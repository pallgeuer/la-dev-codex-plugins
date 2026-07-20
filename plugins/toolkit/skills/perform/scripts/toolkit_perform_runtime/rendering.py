"""Literal prompt inspection and rendering for Perform."""

from .diagnostics import CatalogRequestError

NO_EDITS_PREFIX = "No edits. "


def build_base_prompt(prompt, no_edits):
    """Return the stored prompt with the automatic no-edits prefix applied once."""
    if no_edits:
        return NO_EDITS_PREFIX + prompt
    return prompt


def validate_bindings(prompt_vars, variables):
    """Validate an exact placeholder-to-nonempty-string binding set."""
    if not isinstance(variables, dict):
        raise CatalogRequestError("invalid_variables", "variables must be a JSON object.")
    expected = set(prompt_vars)
    supplied = set(variables)
    missing = sorted(expected - supplied, key=lambda value: value.encode("ascii"))
    extra = sorted(supplied - expected, key=lambda value: str(value).encode("utf-8"))
    if missing:
        raise CatalogRequestError("missing_variables", "Missing prompt-variable bindings: {}.".format(", ".join(missing)))
    if extra:
        raise CatalogRequestError("extra_variables", "Undeclared prompt-variable bindings: {}.".format(", ".join(str(value) for value in extra)))
    for placeholder, value in variables.items():
        if not isinstance(placeholder, str) or not isinstance(value, str) or value == "":
            raise CatalogRequestError("invalid_variable_value", "Every prompt-variable binding must map a declared placeholder string to a nonempty string.")


def validate_qualification(qualification):
    """Normalize and structurally validate optional qualification text."""
    if qualification is None:
        return None
    if not isinstance(qualification, str):
        raise CatalogRequestError("invalid_qualification", "qualification must be null or a string.")
    if any(ord(character) < 32 for character in qualification):
        raise CatalogRequestError("invalid_qualification", "qualification must not contain C0 control characters.")
    normalized = qualification.strip()
    if not normalized:
        raise CatalogRequestError("invalid_qualification", "qualification must contain one nonempty line.")
    if "\r" in normalized or "\n" in normalized:
        raise CatalogRequestError("invalid_qualification", "qualification must be one line without CR or LF characters.")
    if normalized.startswith("BUT:"):
        normalized = normalized[len("BUT:") :].lstrip()
        if not normalized:
            raise CatalogRequestError("invalid_qualification", "qualification must contain text after the optional 'BUT:' prefix.")
    return normalized


def render_prompt(fields, variables, placeholder_pattern, qualification=None):
    """Substitute placeholders once, apply no-edits, and append an optional qualification."""
    prompt_vars = fields["prompt_vars"]
    validate_bindings(prompt_vars, variables)

    def replace(match):
        return variables[match.group(0)]

    substituted = placeholder_pattern.sub(replace, fields["prompt"])
    rendered = build_base_prompt(substituted, fields["no_edits"])
    normalized_qualification = validate_qualification(qualification)
    if normalized_qualification is not None:
        rendered += "\n\nBUT: " + normalized_qualification
    return rendered, normalized_qualification
