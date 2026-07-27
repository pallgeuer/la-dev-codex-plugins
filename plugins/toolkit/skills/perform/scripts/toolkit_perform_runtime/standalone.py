"""High-level standalone launcher facade for Perform actions."""

import functools
from pathlib import Path

from . import action_catalogue, api, validation
from . import catalog as catalog_module
from .diagnostics import PerformRequestError
from .paths import bundled_actions_dir


def _attach_catalog_diagnostics(method):
    """Attach the owning catalog's visible diagnostics to request failures."""

    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except PerformRequestError as error:
            for diagnostic in api.diagnostic_strings(self._catalog):
                if diagnostic not in error.diagnostics:
                    error.diagnostics.append(diagnostic)
            raise

    return wrapped


class StandaloneLauncher:
    """Versioned selection and preparation facade for standalone launchers."""

    __slots__ = ("_catalog",)

    def __init__(self, catalog):
        """Store one loaded action catalog."""
        if not isinstance(catalog, catalog_module.ActionCatalog):
            raise TypeError("catalog must be an ActionCatalog")
        self._catalog = catalog

    @property
    def precedence_incomplete(self):
        """Return whether catalog precedence is unsafe for action selection."""
        return self._catalog.precedence_incomplete

    def _parse_request(self, action, language=None):
        """Normalize one action and optional language without catalog lookup."""
        if language is not None and not catalog_module.is_language_name(language):
            raise PerformRequestError("invalid_language", "Language values must match {} without trimming.".format(catalog_module.LANGUAGE_NAME_REGEX))
        if isinstance(action, str) and validation.full_match(catalog_module.STRICT_SELECTOR_PATTERN, action):
            name, selector_language, selector = catalog_module.parse_selector(action)
            if language is not None and language != selector_language:
                raise PerformRequestError("conflicting_language", "Strict selector {} conflicts with --language {!r}.".format(selector, language))
            return name, selector_language, selector, True
        if not catalog_module.is_action_name(action):
            raise PerformRequestError("invalid_selector", "Expected a bare action name or strict ACTION[LANGUAGE] selector.")
        selector = None if language is None else "{}[{}]".format(action, language)
        return action, language, selector, False

    def _resolve_selector(self, action, language=None):
        """Resolve one deterministic action request to a canonical selector."""
        name, _requested_language, requested_selector, _strict = self._parse_request(action, language=language)
        if name == "help":
            if requested_selector in (None, catalog_module.HELP_SELECTOR):
                return catalog_module.HELP_SELECTOR
            raise PerformRequestError("not_found", "No effective action matches strict selector {}.".format(requested_selector), alternatives=[catalog_module.HELP_SELECTOR])
        if self._catalog.precedence_incomplete:
            raise PerformRequestError("fatal_catalog", "Catalog precedence is incomplete; fix the fatal discovery or file diagnostic before selecting an action.")
        summaries = self._catalog.list_actions(name=name)
        if requested_selector is not None:
            available = [summary.selector for summary in summaries]
            if requested_selector not in available:
                raise PerformRequestError("not_found", "No effective action matches strict selector {}.".format(requested_selector), alternatives=available)
            return requested_selector
        if len(summaries) == 1:
            return summaries[0].selector
        agnostic = "{}[agnostic]".format(name)
        if any(summary.selector == agnostic for summary in summaries):
            return agnostic
        available = [summary.selector for summary in summaries]
        if not available:
            raise PerformRequestError("not_found", "No effective action is named {!r}.".format(name))
        raise PerformRequestError("ambiguous_language", "Action {!r} has multiple language variants; use --language or a strict selector.".format(name), alternatives=available)

    @_attach_catalog_diagnostics
    def list_actions(self, action=None, language=None):
        """Return one filtered JSON-ready action-summary payload."""
        if action is not None:
            name, requested_language, requested_selector, _strict = self._parse_request(action, language=language)
            available = self._catalog.list_actions(name=name)
            if requested_selector is not None:
                variants = [summary for summary in available if summary.selector == requested_selector]
            elif requested_language is not None:
                variants = [summary for summary in available if summary.language == requested_language]
            else:
                variants = available
        else:
            if language is not None and not catalog_module.is_language_name(language):
                raise PerformRequestError("invalid_language", "Language values must match {} without trimming.".format(catalog_module.LANGUAGE_NAME_REGEX))
            variants = self._catalog.list_actions()
            if language is not None:
                variants = [summary for summary in variants if summary.language == language]
        payload = {"variants": [summary.to_dict() for summary in variants]}
        return api.response_payload(self._catalog, result=payload)

    @_attach_catalog_diagnostics
    def show_action(self, action, language=None):
        """Return one JSON-ready built-in help or launch-configuration payload."""
        selector = self._resolve_selector(action, language=language)
        if selector == catalog_module.HELP_SELECTOR:
            references = Path(__file__).resolve().parents[2] / "references"
            guide_records = (
                ("action_files", "Define, discover, layer, validate, and catalogue Perform actions.", "action_files.md"),
                ("codex_skill", "Select and run Perform actions inside an existing Codex chat.", "codex_skill.md"),
                ("standalone_cli", "Select and launch Perform actions with codex-perform or its Python API.", "standalone_cli.md"),
            )
            guides = [{"name": name, "description": description, "path": str(references / filename)} for name, description, filename in guide_records]
            payload = {"selector": catalog_module.HELP_SELECTOR, "help": "Read the installed Perform guides.", "guides": guides}
        else:
            payload = self._catalog.launch_config(selector).to_dict()
        return api.response_payload(self._catalog, result=payload)

    @_attach_catalog_diagnostics
    def write_action_catalogue(self, output=None):
        """Safely update a stable Markdown catalogue of effective actions."""
        payload = action_catalogue.write_action_catalogue(self._catalog, output=output)
        return api.response_payload(self._catalog, result=payload)

    @_attach_catalog_diagnostics
    def prepare_launch(self, action, language=None, variable_bindings=None, qualification=None):
        """Select and render one action from raw launcher inputs."""
        selector = self._resolve_selector(action, language=language)
        variables = validation.parse_variable_bindings([] if variable_bindings is None else variable_bindings)
        return self._catalog.prepare_launch(selector, variables, qualification=qualification)


def load_standalone_launcher(cwd, env=None):
    """Load conventional action sources into the standalone facade."""
    catalog = catalog_module.load_action_catalog(bundled_dir=bundled_actions_dir(), cwd=cwd, env=env)
    return StandaloneLauncher(catalog)


__all__ = ("StandaloneLauncher", "load_standalone_launcher")
