"""Version 1 Perform catalog parsing, layering, and materialization."""

import copy
import json
import re
import unicodedata
from pathlib import Path

from . import diagnostics as diagnostics_module
from . import rendering
from .diagnostics import CatalogRequestError, Diagnostic, json_pointer_component, sorted_unique_diagnostics
from .discovery import discover_action_directories, explicit_discovery

ACTION_NAME_REGEX = r"^[a-z0-9][a-z0-9._-]*$"
LANGUAGE_NAME_REGEX = r"^[a-z0-9][a-z0-9.+_-]*$"
MODEL_REGEX = r"^[A-Za-z0-9][A-Za-z0-9._:+/-]*$"
EFFORT_REGEX = r"^[a-z][a-z0-9_-]*$"
PLACEHOLDER_REGEX = r"%[A-Za-z][A-Za-z0-9_]*%"
STRICT_SELECTOR_REGEX = r"^([a-z0-9][a-z0-9._-]*)\[([a-z0-9][a-z0-9.+_-]*)\]$"

ACTION_NAME_PATTERN = re.compile(ACTION_NAME_REGEX)
LANGUAGE_NAME_PATTERN = re.compile(LANGUAGE_NAME_REGEX)
MODEL_PATTERN = re.compile(MODEL_REGEX)
EFFORT_PATTERN = re.compile(EFFORT_REGEX)
PLACEHOLDER_PATTERN = re.compile(PLACEHOLDER_REGEX)
STRICT_SELECTOR_PATTERN = re.compile(STRICT_SELECTOR_REGEX)

ACTION_FIELDS = (
    "gloss",
    "model",
    "reasoning_effort",
    "goal_mode",
    "plan_mode",
    "plan_reasoning_effort",
    "no_edits",
    "prompt_vars",
    "prompt",
    "prefer_interactive",
    "custom_codex_args",
    "notes",
)
ACTION_FIELD_SET = frozenset(ACTION_FIELDS)
ROOT_FIELDS = frozenset(("version", "ignore_actions", "actions"))
HELP_SELECTOR = "help[agnostic]"
HELP_GLOSS = "Explain Perform and its action-file format"
HELP_MESSAGE = "Read references/action-files.md for the immutable built-in help action."
RESERVED_CODEX_CONFIG_KEYS = frozenset(("model", "model_reasoning_effort", "plan_mode_reasoning_effort"))
NO_EDITS_SENTENCE = "No edits."


class DuplicateKeyError(ValueError):
    """A JSON object repeated a key and is therefore ambiguous."""

    def __init__(self, key):
        """Store the repeated key."""
        super().__init__("Duplicate JSON key: {!r}".format(key))
        self.key = key


def _full_match(pattern, value):
    """Match a documented anchored regex without dollar-before-newline behavior."""
    match = pattern.match(value)
    return match is not None and match.end() == len(value)


def is_action_name(value):
    """Return whether a value is a valid bare action name."""
    return isinstance(value, str) and _full_match(ACTION_NAME_PATTERN, value)


def is_language_name(value):
    """Return whether a value is a valid language component."""
    return isinstance(value, str) and _full_match(LANGUAGE_NAME_PATTERN, value)


def parse_selector(value):
    """Parse and canonicalize one strict ACTION[LANGUAGE] selector."""
    if not isinstance(value, str):
        raise CatalogRequestError("invalid_selector", "The selector must be a string.")
    match = STRICT_SELECTOR_PATTERN.match(value)
    if match is None or match.end() != len(value):
        raise CatalogRequestError("invalid_selector", "Expected a strict ACTION[LANGUAGE] selector using the documented ASCII grammar.")
    return match.group(1), match.group(2), "{}[{}]".format(match.group(1), match.group(2))


def parse_ignore_selector(value):
    """Return action and optional language for one ignore selector."""
    if is_action_name(value):
        return value, None
    action, language, _canonical = parse_selector(value)
    return action, language


def _unique_pairs(pairs):
    """Build one JSON object while rejecting duplicate keys."""
    value = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateKeyError(key)
        value[key] = item
    return value


def loads_unique_json(text):
    """Decode JSON with duplicate-key detection at every object depth."""
    return json.loads(text, object_pairs_hook=_unique_pairs)


def _contains_display_control(value):
    """Return whether short display metadata contains a control or line separator."""
    return any(unicodedata.category(character) in ("Cc", "Zl", "Zp") for character in value)


def _reserved_config_key(key):
    """Return whether one Codex config key belongs to structured action policy."""
    return any(key == reserved or key.startswith(reserved + ".") for reserved in RESERVED_CODEX_CONFIG_KEYS)


def _validate_custom_codex_args(value):
    """Return an optional code and message for invalid or conflicting Codex arguments."""
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return "invalid_custom_codex_args", "custom_codex_args must be a list containing only strings."
    if any(not item or "\x00" in item for item in value):
        return "invalid_custom_codex_args", "custom_codex_args entries must be nonempty strings without NUL characters."

    index = 0
    while index < len(value):
        argument = value[index]
        if argument in ("-m", "--model") or (argument.startswith("-m") and not argument.startswith("--")) or argument.startswith("--model="):
            return "conflicting_custom_codex_args", "custom_codex_args must not override model; use the structured model field."

        assignment = None
        if argument in ("-c", "--config"):
            if index + 1 >= len(value):
                return "invalid_custom_codex_args", "-c and --config in custom_codex_args require a following key=value argument."
            assignment = value[index + 1]
            index += 1
        elif argument.startswith("--config="):
            assignment = argument[len("--config=") :]
        elif argument.startswith("-c") and not argument.startswith("--"):
            assignment = argument[2:]
            if assignment.startswith("="):
                assignment = assignment[1:]

        if assignment is not None:
            key, separator, _configured_value = assignment.partition("=")
            key = key.strip()
            if not separator or not key:
                return "invalid_custom_codex_args", "Codex config overrides in custom_codex_args must use key=value syntax."
            if _reserved_config_key(key):
                return "conflicting_custom_codex_args", "custom_codex_args must not override reserved config key {!r}; use its structured action field.".format(key)
        index += 1
    return None, None


def _has_manual_no_edits_prefix(prompt):
    """Return whether a prompt starts with the mechanically supplied sentence."""
    return prompt.startswith(NO_EDITS_SENTENCE) and (len(prompt) == len(NO_EDITS_SENTENCE) or prompt[len(NO_EDITS_SENTENCE)].isspace())


class _FieldOrigin:
    """Internal source location for one applied action field or definition."""

    __slots__ = ("filename", "filename_sort_key", "json_path", "source")

    def __init__(self, source, filename, json_path):
        """Store a coherent file and JSON location with precedence metadata."""
        self.source = source
        self.filename = filename
        self.json_path = json_path
        self.filename_sort_key = filename.encode("utf-8", errors="surrogateescape")

    def rank(self):
        """Return the deterministic application rank used for causal errors."""
        return self.source.source_order, self.filename_sort_key


class VariantPatch:
    """Accumulated fields and latest definition origin for one selector."""

    __slots__ = ("definition_origin", "field_origins", "fields")

    def __init__(self, fields=None, field_origins=None, definition_origin=None):
        """Store accumulated fields and the latest definition origin."""
        self.fields = copy.deepcopy(fields or {})
        self.field_origins = dict(field_origins or {})
        self.definition_origin = definition_origin

    def overlay(self, fields, field_origins, definition_origin):
        """Replace supplied fields wholesale while retaining lower unspecified fields."""
        for field, value in fields.items():
            self.fields[field] = copy.deepcopy(value)
            self.field_origins[field] = field_origins[field]
        self.definition_origin = definition_origin


class ActionSummary:
    """Selection metadata for one effective action variant."""

    __slots__ = ("gloss", "language", "name", "prompt_vars", "selector")

    def __init__(self, name, language, gloss, prompt_vars):
        """Store the fields needed for deterministic narrowing and semantic selection."""
        self.name = name
        self.language = language
        self.selector = "{}[{}]".format(name, language)
        self.gloss = gloss
        self.prompt_vars = copy.deepcopy(prompt_vars)

    def to_dict(self):
        """Return only the metadata consumed during selection."""
        result = {"selector": self.selector, "gloss": self.gloss}
        if self.prompt_vars:
            result["prompt_vars"] = copy.deepcopy(self.prompt_vars)
        return result


class EffectiveAction:
    """Fully materialized and validated action variant."""

    __slots__ = ("fields", "language", "name", "selector")

    def __init__(self, name, language, fields):
        """Store immutable-by-convention effective action data."""
        self.name = name
        self.language = language
        self.selector = "{}[{}]".format(name, language)
        self.fields = copy.deepcopy(fields)

    def summary(self):
        """Return selection metadata for this effective action."""
        return ActionSummary(
            name=self.name,
            language=self.language,
            gloss=self.fields["gloss"],
            prompt_vars=self.fields["prompt_vars"],
        )


class ActionInspection:
    """Exact base prompt and metadata shown before semantic binding."""

    __slots__ = ("action", "base_prompt")

    def __init__(self, action, base_prompt):
        """Store an inspected action and its automatically prefixed base prompt."""
        self.action = action
        self.base_prompt = base_prompt

    def to_dict(self):
        """Return only the details consumed while preparing execution."""
        fields = self.action.fields
        if fields["plan_mode"]:
            mode = "plan"
        elif fields["goal_mode"]:
            mode = "goal"
        else:
            mode = "default"
        result = {"prompt": self.base_prompt, "mode": mode}
        if fields["prompt_vars"]:
            result["prompt_vars"] = copy.deepcopy(fields["prompt_vars"])
        if fields["notes"]:
            result["notes"] = fields["notes"]
        return result


class BuiltInHelpResult:
    """Normal inspection result for immutable built-in help."""

    __slots__ = ()

    def to_dict(self):
        """Return the reference instruction consumed by Perform."""
        return {"help": HELP_MESSAGE}


class RenderedAction:
    """Final prompt plus user-facing metadata kept outside it."""

    __slots__ = ("action", "prompt", "qualification")

    def __init__(self, action, prompt, qualification):
        """Store final literal prompt and normalized optional qualification."""
        self.action = action
        self.prompt = prompt
        self.qualification = qualification

    def to_dict(self):
        """Return the authoritative rendered prompt."""
        return {"prompt": self.prompt}


def _file_diagnostic(source, filename, code, message, severity="error", json_path=None, selector=None, fatality="file_fatal"):
    """Create a diagnostic with file and deterministic precedence metadata."""
    return Diagnostic(
        severity=severity,
        code=code,
        message=message,
        source_file=str(Path(source.display_path) / filename),
        json_path=json_path,
        selector=selector,
        fatality=fatality,
        source_order=source.source_order,
        filename_sort_key=filename.encode("utf-8", errors="surrogateescape"),
    )


def _origin_for_fields(field_origins, definition_origin, implicated_fields):
    """Choose the latest implicated origin, with later arguments breaking ties."""
    selected = None
    for field in implicated_fields:
        origin = field_origins.get(field)
        if origin is not None and (selected is None or origin.rank() >= selected.rank()):
            selected = origin
    return definition_origin if selected is None else selected


def _origin_diagnostic(field_origins, definition_origin, implicated_fields, action, language, code, message):
    """Create one variant-local diagnostic at a coherent causal location."""
    origin = _origin_for_fields(field_origins, definition_origin, implicated_fields)
    return _file_diagnostic(origin.source, origin.filename, code, message, json_path=origin.json_path, selector="{}[{}]".format(action, language), fatality="variant_fatal")


def _validate_prompt_variables(prompt_vars, prompt, field_origins, definition_origin, action, language, diagnostics):
    """Validate declaration/use agreement in one materialized prompt."""
    declared = set(prompt_vars)
    used = set(PLACEHOLDER_PATTERN.findall(prompt))
    missing_from_prompt = sorted(declared - used, key=lambda value: value.encode("ascii"))
    undeclared = sorted(used - declared, key=lambda value: value.encode("ascii"))
    for placeholder in missing_from_prompt:
        diagnostics.append(
            _origin_diagnostic(
                field_origins,
                definition_origin,
                ("prompt", "prompt_vars"),
                action,
                language,
                "unused_prompt_variable",
                "Declared placeholder {} does not occur in the materialized prompt.".format(placeholder),
            )
        )
    for placeholder in undeclared:
        diagnostics.append(
            _origin_diagnostic(
                field_origins, definition_origin, ("prompt_vars", "prompt"), action, language, "undeclared_prompt_variable", "Prompt placeholder {} is not declared in prompt_vars.".format(placeholder)
            )
        )


def _validate_fields(fields, field_origins, definition_origin, action, language, complete):
    """Validate supplied fields locally or a fully materialized action."""
    diagnostics = []
    selector = "{}[{}]".format(action, language)
    unknown = sorted(set(fields) - ACTION_FIELD_SET, key=lambda value: diagnostics_module.unicode_sort_key(str(value)))
    diagnostics.extend(
        _origin_diagnostic(field_origins, definition_origin, (field,), action, language, "unknown_action_field", "Unknown version 1 action field {!r}.".format(field)) for field in unknown
    )
    if unknown:
        return diagnostics

    if complete:
        missing = [field for field in ACTION_FIELDS if field not in fields]
        if missing:
            diagnostics.append(
                _origin_diagnostic(field_origins, definition_origin, (), action, language, "incomplete_action", "Materialized {} is missing required fields: {}.".format(selector, ", ".join(missing)))
            )
            return diagnostics

    for field, value in fields.items():
        if field == "gloss":
            if not isinstance(value, str) or not value.strip() or _contains_display_control(value):
                diagnostics.append(
                    _origin_diagnostic(
                        field_origins, definition_origin, (field,), action, language, "invalid_gloss", "gloss must be a nonempty single-line string without Unicode control or separator characters."
                    )
                )
        elif field == "model":
            if not isinstance(value, str) or (value != "default" and not _full_match(MODEL_PATTERN, value)):
                diagnostics.append(
                    _origin_diagnostic(
                        field_origins, definition_origin, (field,), action, language, "invalid_model", "model must be exactly 'default' or match {} without trimming.".format(MODEL_REGEX)
                    )
                )
        elif field in ("reasoning_effort", "plan_reasoning_effort"):
            if not isinstance(value, str) or not _full_match(EFFORT_PATTERN, value):
                diagnostics.append(_origin_diagnostic(field_origins, definition_origin, (field,), action, language, "invalid_effort", "{} must match {} without trimming.".format(field, EFFORT_REGEX)))
        elif field in ("goal_mode", "plan_mode", "no_edits", "prefer_interactive"):
            if type(value) is not bool:
                diagnostics.append(_origin_diagnostic(field_origins, definition_origin, (field,), action, language, "invalid_boolean", "{} must be a JSON Boolean.".format(field)))
        elif field == "prompt_vars":
            if not isinstance(value, dict):
                diagnostics.append(_origin_diagnostic(field_origins, definition_origin, (field,), action, language, "invalid_prompt_vars", "prompt_vars must be an object."))
            else:
                for placeholder, description in value.items():
                    if not isinstance(placeholder, str) or not _full_match(PLACEHOLDER_PATTERN, placeholder):
                        diagnostics.append(
                            _origin_diagnostic(field_origins, definition_origin, (field,), action, language, "invalid_placeholder", "Prompt variable keys must match {}.".format(PLACEHOLDER_REGEX))
                        )
                    if not isinstance(description, str) or not description.strip() or _contains_display_control(description):
                        diagnostics.append(
                            _origin_diagnostic(
                                field_origins,
                                definition_origin,
                                (field,),
                                action,
                                language,
                                "invalid_placeholder_description",
                                "Every prompt variable description must be a nonempty single-line string without Unicode control or separator characters.",
                            )
                        )
        elif field == "prompt":
            if not isinstance(value, str) or not value.strip():
                diagnostics.append(_origin_diagnostic(field_origins, definition_origin, (field,), action, language, "invalid_prompt", "prompt must be a nonempty string after trimming."))
        elif field == "custom_codex_args":
            code, message = _validate_custom_codex_args(value)
            if code is not None:
                diagnostics.append(_origin_diagnostic(field_origins, definition_origin, (field,), action, language, code, message))
        elif field == "notes" and not isinstance(value, str):
            diagnostics.append(_origin_diagnostic(field_origins, definition_origin, (field,), action, language, "invalid_notes", "notes must be a string."))

    goal_mode = fields.get("goal_mode")
    plan_mode = fields.get("plan_mode")
    if goal_mode is True and plan_mode is True:
        diagnostics.append(_origin_diagnostic(field_origins, definition_origin, ("goal_mode", "plan_mode"), action, language, "conflicting_modes", "goal_mode and plan_mode cannot both be true."))
    if plan_mode is False and "reasoning_effort" in fields and "plan_reasoning_effort" in fields and fields["reasoning_effort"] != fields["plan_reasoning_effort"]:
        diagnostics.append(
            _origin_diagnostic(
                field_origins,
                definition_origin,
                ("plan_mode", "reasoning_effort", "plan_reasoning_effort"),
                action,
                language,
                "unequal_efforts_without_plan",
                "reasoning_effort and plan_reasoning_effort must be equal when plan_mode is false.",
            )
        )
    if fields.get("no_edits") is True and isinstance(fields.get("prompt"), str) and _has_manual_no_edits_prefix(fields["prompt"]):
        diagnostics.append(
            _origin_diagnostic(
                field_origins,
                definition_origin,
                ("no_edits", "prompt"),
                action,
                language,
                "manual_no_edits_prefix",
                "Remove the manual 'No edits.' prefix; rendering adds it automatically when no_edits is true.",
            )
        )
    if complete and isinstance(fields.get("prompt_vars"), dict) and isinstance(fields.get("prompt"), str):
        _validate_prompt_variables(fields["prompt_vars"], fields["prompt"], field_origins, definition_origin, action, language, diagnostics)
    return diagnostics


def _load_json_file(source, filename):
    """Decode and root-validate one action file, returning data and diagnostics."""
    path = Path(source.normalized_path) / filename
    try:
        with path.open("rb") as stream:
            raw = stream.read()
    except OSError as exc:
        return None, [_file_diagnostic(source, filename, "action_file_unreadable", "Could not read action file: {}".format(exc), fatality="catalog_fatal")]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return None, [_file_diagnostic(source, filename, "invalid_utf8", "Action file is not valid UTF-8: {}".format(exc))]
    try:
        data = loads_unique_json(text)
    except DuplicateKeyError as exc:
        return None, [_file_diagnostic(source, filename, "duplicate_key", "Action file contains duplicate key {!r}; the entire file was ignored.".format(exc.key))]
    except (TypeError, ValueError) as exc:
        return None, [_file_diagnostic(source, filename, "invalid_json", "Action file is not valid JSON: {}".format(exc))]
    if not isinstance(data, dict):
        return None, [_file_diagnostic(source, filename, "invalid_root", "The version 1 root must be a JSON object.", json_path="")]
    unknown_root = sorted(set(data) - ROOT_FIELDS, key=lambda value: diagnostics_module.unicode_sort_key(str(value)))
    if unknown_root:
        return None, [
            _file_diagnostic(source, filename, "unknown_root_field", "Unknown version 1 root fields make the file unusable: {}.".format(", ".join(repr(field) for field in unknown_root)), json_path="")
        ]
    if "version" not in data or type(data["version"]) is not int:
        return None, [_file_diagnostic(source, filename, "invalid_version", "version is required and must be the integer 1, not a Boolean.", json_path="/version")]
    if data["version"] != 1:
        return None, [_file_diagnostic(source, filename, "unsupported_version", "Unsupported action-file version {!r}; only version 1 is supported.".format(data["version"]), json_path="/version")]
    if "actions" not in data or not isinstance(data["actions"], dict):
        return None, [_file_diagnostic(source, filename, "invalid_actions_root", "actions is required and must be an object.", json_path="/actions")]
    if "ignore_actions" in data and not isinstance(data["ignore_actions"], list):
        return None, [_file_diagnostic(source, filename, "invalid_ignore_actions", "ignore_actions must be a list when present.", json_path="/ignore_actions")]
    if "ignore_actions" not in data:
        data["ignore_actions"] = []
    return data, []


def _apply_file(data, source, filename, patches, diagnostics):
    """Apply one root-trusted file's ignores then valid definitions."""
    for index, ignore_selector in enumerate(data["ignore_actions"]):
        path = "/ignore_actions/{}".format(index)
        if not isinstance(ignore_selector, str):
            diagnostics.append(_file_diagnostic(source, filename, "invalid_ignore_selector", "Ignore selectors must be strings using ACTION or ACTION[LANGUAGE].", json_path=path, fatality="nonfatal"))
            continue
        try:
            action, language = parse_ignore_selector(ignore_selector)
        except CatalogRequestError:
            diagnostics.append(
                _file_diagnostic(
                    source, filename, "invalid_ignore_selector", "Invalid ignore selector {!r}; expected ACTION or ACTION[LANGUAGE].".format(ignore_selector), json_path=path, fatality="nonfatal"
                )
            )
            continue
        if action == "help":
            diagnostics.append(
                _file_diagnostic(source, filename, "reserved_help_ignore", "The immutable built-in help action cannot be ignored.", json_path=path, selector=ignore_selector, fatality="nonfatal")
            )
            continue
        if language is None:
            for identity in [identity for identity in patches if identity[0] == action]:
                del patches[identity]
        else:
            patches.pop((action, language), None)

    for action, languages in data["actions"].items():
        action_path = "/actions/{}".format(json_pointer_component(str(action)))
        if not is_action_name(action):
            diagnostics.append(
                _file_diagnostic(
                    source, filename, "invalid_action_name", "Action names must match {}.".format(ACTION_NAME_REGEX), json_path=action_path, selector=str(action), fatality="variant_fatal"
                )
            )
            continue
        if action == "help":
            diagnostics.append(
                _file_diagnostic(
                    source, filename, "reserved_help_definition", "The immutable built-in help action cannot be defined or overridden.", json_path=action_path, selector="help", fatality="nonfatal"
                )
            )
            continue
        if not isinstance(languages, dict) or not languages:
            diagnostics.append(
                _file_diagnostic(
                    source,
                    filename,
                    "invalid_action_languages",
                    "Each action must contain a nonempty object of language implementations.",
                    json_path=action_path,
                    selector=action,
                    fatality="variant_fatal",
                )
            )
            continue
        for language, fields in languages.items():
            language_path = "{}/{}".format(action_path, json_pointer_component(str(language)))
            selector = "{}[{}]".format(action, language)
            if not is_language_name(language):
                diagnostics.append(
                    _file_diagnostic(
                        source, filename, "invalid_language_name", "Language names must match {}.".format(LANGUAGE_NAME_REGEX), json_path=language_path, selector=selector, fatality="variant_fatal"
                    )
                )
                continue
            if not isinstance(fields, dict) or not fields:
                diagnostics.append(
                    _file_diagnostic(
                        source,
                        filename,
                        "invalid_language_fields",
                        "Each language implementation must contain a nonempty object of fields.",
                        json_path=language_path,
                        selector=selector,
                        fatality="variant_fatal",
                    )
                )
                continue
            definition_origin = _FieldOrigin(source, filename, language_path)
            field_origins = {field: _FieldOrigin(source, filename, "{}/{}".format(language_path, json_pointer_component(str(field)))) for field in fields}
            complete = language == "agnostic"
            field_diagnostics = _validate_fields(fields, field_origins, definition_origin, action, language, complete=complete)
            diagnostics.extend(field_diagnostics)
            if field_diagnostics:
                continue
            identity = (action, language)
            if language == "agnostic" or identity not in patches:
                patches[identity] = VariantPatch(fields=fields, field_origins=field_origins, definition_origin=definition_origin)
            else:
                patches[identity].overlay(fields, field_origins, definition_origin)


def _materialize(patches, diagnostics):
    """Apply agnostic inheritance and final validation to accumulated patches."""
    actions = {}
    action_names = sorted({identity[0] for identity in patches}, key=lambda value: value.encode("ascii"))
    for action in action_names:
        languages = sorted((identity[1] for identity in patches if identity[0] == action), key=lambda value: value.encode("ascii"))
        base = patches.get((action, "agnostic"))
        for language in languages:
            patch = patches[(action, language)]
            if language == "agnostic":
                fields = copy.deepcopy(patch.fields)
                field_origins = dict(patch.field_origins)
            else:
                fields = copy.deepcopy(base.fields) if base is not None else {}
                field_origins = dict(base.field_origins) if base is not None else {}
                for field, value in patch.fields.items():
                    fields[field] = copy.deepcopy(value)
                    field_origins[field] = patch.field_origins[field]
            final_diagnostics = _validate_fields(fields, field_origins, patch.definition_origin, action, language, complete=True)
            diagnostics.extend(final_diagnostics)
            if final_diagnostics:
                continue
            actions[(action, language)] = EffectiveAction(action, language, fields)
    return actions


class ActionCatalog:
    """Effective Perform actions, diagnostics, discovery, and rendering API."""

    __slots__ = ("_actions", "diagnostics", "discovery", "precedence_incomplete")

    def __init__(self, actions, diagnostics, discovery, precedence_incomplete=False):
        """Store fully materialized variants and deterministic diagnostics."""
        self._actions = dict(actions)
        self.diagnostics = sorted_unique_diagnostics(list(discovery.diagnostics) + list(diagnostics))
        self.discovery = discovery
        self.precedence_incomplete = precedence_incomplete or discovery.precedence_incomplete or any(diagnostic.fatal for diagnostic in self.diagnostics)

    def list_actions(self, name=None):
        """Return all summaries or variants of one exact bare action name."""
        if name is not None and not is_action_name(name):
            raise CatalogRequestError("invalid_name", "Action-name filters must match {}.".format(ACTION_NAME_REGEX))
        summaries = [action.summary() for action in self._actions.values() if name is None or action.name == name]
        if name is None or name == "help":
            summaries.append(ActionSummary("help", "agnostic", HELP_GLOSS, {}))
        return sorted(summaries, key=lambda summary: (summary.name.encode("ascii"), summary.language.encode("ascii")))

    def _require_complete_precedence(self):
        """Reject prompt-sensitive operations when an override source is unknowable."""
        if self.precedence_incomplete:
            raise CatalogRequestError("fatal_catalog", "Catalog precedence is incomplete; fix the fatal discovery or file diagnostic before inspecting or rendering an action.")

    def inspect(self, selector):
        """Return the exact effective base prompt for one strict selector."""
        name, language, canonical = parse_selector(selector)
        if canonical == HELP_SELECTOR:
            return BuiltInHelpResult()
        self._require_complete_precedence()
        action = self._actions.get((name, language))
        if action is None:
            alternatives = [summary.selector for summary in self.list_actions(name=name)]
            raise CatalogRequestError("not_found", "No effective action matches strict selector {}.".format(canonical), alternatives=alternatives)
        return ActionInspection(action, rendering.build_base_prompt(action.fields["prompt"], action.fields["no_edits"]))

    def render(self, selector, variables, qualification=None):
        """Render one exact action after binding and qualification validation."""
        inspection = self.inspect(selector)
        if isinstance(inspection, BuiltInHelpResult):
            raise CatalogRequestError("not_executable", "The immutable built-in help action cannot be rendered; inspect it instead.")
        prompt, normalized_qualification = rendering.render_prompt(inspection.action.fields, variables, PLACEHOLDER_PATTERN, qualification)
        return RenderedAction(inspection.action, prompt, normalized_qualification)


def _list_source_files(source, diagnostics):
    """Return direct JSON filenames in exact UTF-8 byte order."""
    try:
        entries = list(Path(source.normalized_path).iterdir())
    except OSError as exc:
        diagnostics.append(
            Diagnostic(
                severity="error",
                code="action_source_unreadable",
                message="Could not enumerate applicable {} action source {}: {}".format(source.kind, source.display_path, exc),
                source_file=source.display_path,
                fatality="catalog_fatal",
                source_order=source.source_order,
            )
        )
        return []
    filenames = []
    for entry in entries:
        name = entry.name
        try:
            encoded = name.encode("utf-8")
        except UnicodeEncodeError:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="unencodable_action_filename",
                    message="An action filename cannot be sorted as UTF-8 bytes in {}.".format(source.display_path),
                    source_file=source.display_path,
                    fatality="catalog_fatal",
                    source_order=source.source_order,
                )
            )
            continue
        if name.endswith(".json") and entry.is_file():
            filenames.append((encoded, name))
    return [name for _encoded, name in sorted(filenames, key=lambda item: item[0])]


def load_action_catalog(bundled_dir=None, cwd=None, env=None, action_directories=None, filesystem=None, git_runner=None, system_config_path="/etc/codex/config.toml"):
    """Discover or explicitly load action directories into one effective catalog."""
    if action_directories is not None:
        discovery = explicit_discovery(action_directories)
    else:
        if bundled_dir is None:
            raise ValueError("bundled_dir is required when action_directories is not supplied")
        discovery = discover_action_directories(
            bundled_dir=bundled_dir,
            cwd=cwd,
            env=env,
            filesystem=filesystem,
            git_runner=git_runner,
            system_config_path=system_config_path,
        )
    patches = {}
    diagnostics = []
    for source in discovery.sources:
        for filename in _list_source_files(source, diagnostics):
            data, file_diagnostics = _load_json_file(source, filename)
            diagnostics.extend(file_diagnostics)
            if data is not None:
                _apply_file(data, source, filename, patches, diagnostics)
    actions = _materialize(patches, diagnostics)
    return ActionCatalog(actions, diagnostics, discovery)
