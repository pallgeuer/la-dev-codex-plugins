"""Small public API and versioned machine protocol for Perform."""

import copy

from .catalog import ACTION_NAME_REGEX, HELP_GLOSS, HELP_SELECTOR, ActionCatalog, CatalogRequestError, DuplicateKeyError, is_action_name, load_action_catalog, loads_unique_json, parse_selector

SCHEMA_VERSION = 1
MAX_REQUEST_BYTES = 1_048_576
INSPECT_REQUEST_FIELDS = frozenset(("schema_version", "operation", "selector"))
RENDER_REQUEST_FIELDS = frozenset(("schema_version", "operation", "selector", "variables", "qualification"))


def decode_request_bytes(raw):
    """Decode and validate one bounded UTF-8 JSON request object."""
    if not isinstance(raw, bytes):
        raise CatalogRequestError("invalid_request", "The machine request must be supplied as bytes from stdin.")
    if len(raw) > MAX_REQUEST_BYTES:
        raise CatalogRequestError("request_too_large", "The stdin JSON request exceeds 1,048,576 bytes.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CatalogRequestError("invalid_request_utf8", "The stdin request is not valid UTF-8: {}".format(exc)) from exc
    try:
        request = loads_unique_json(text)
    except DuplicateKeyError as exc:
        raise CatalogRequestError("duplicate_request_key", "The stdin request contains duplicate key {!r}.".format(exc.key)) from exc
    except (TypeError, ValueError) as exc:
        raise CatalogRequestError("invalid_request_json", "The stdin request must contain exactly one JSON value followed only by whitespace: {}".format(exc)) from exc
    if not isinstance(request, dict):
        raise CatalogRequestError("invalid_request", "The stdin request root must be a JSON object.")
    return request


def validate_request(request):
    """Validate exact version 1 request fields and return a defensive copy."""
    if not isinstance(request, dict):
        raise CatalogRequestError("invalid_request", "The request root must be a JSON object.")
    if type(request.get("schema_version")) is not int or request.get("schema_version") != SCHEMA_VERSION:
        raise CatalogRequestError("invalid_schema_version", "schema_version must be the integer 1, not a Boolean.")
    operation = request.get("operation")
    if operation == "inspect":
        expected_fields = INSPECT_REQUEST_FIELDS
    elif operation == "render":
        expected_fields = RENDER_REQUEST_FIELDS
    else:
        raise CatalogRequestError("invalid_operation", "operation must be exactly 'inspect' or 'render'.")
    missing = sorted(expected_fields - set(request))
    unknown = sorted(set(request) - expected_fields)
    if missing:
        raise CatalogRequestError("missing_request_fields", "Missing {} request fields: {}.".format(operation, ", ".join(missing)))
    if unknown:
        raise CatalogRequestError("unknown_request_fields", "Unknown {} request fields: {}.".format(operation, ", ".join(unknown)))
    parse_selector(request["selector"])
    if operation == "render":
        if not isinstance(request["variables"], dict):
            raise CatalogRequestError("invalid_variables", "variables must be a JSON object.")
        if request["qualification"] is not None and not isinstance(request["qualification"], str):
            raise CatalogRequestError("invalid_qualification", "qualification must be null or a string.")
    return copy.deepcopy(request)


def process_request(catalog, request):
    """Inspect or render through one already loaded catalog."""
    if not isinstance(catalog, ActionCatalog):
        raise TypeError("catalog must be an ActionCatalog")
    validated = validate_request(request)
    if validated["operation"] == "inspect":
        inspection = catalog.inspect(validated["selector"])
        return inspection.to_dict()
    rendered = catalog.render(
        selector=validated["selector"],
        variables=validated["variables"],
        qualification=validated["qualification"],
    )
    return rendered.to_dict()


def response_envelope(catalog, status, result=None):
    """Build the versioned JSON response envelope shared by bundled scripts."""
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "discovery": catalog.discovery.to_dict(),
        "diagnostics": [diagnostic.to_dict() for diagnostic in catalog.diagnostics],
        "result": {} if result is None else result,
    }


def error_result(error):
    """Return JSON-ready request error details."""
    if isinstance(error, CatalogRequestError):
        return error.to_dict()
    return {"message": str(error), "selector": None, "available_variants": []}


def built_in_help_result():
    """Return the immutable listing descriptor used by help orchestration."""
    return {
        "selector": HELP_SELECTOR,
        "name": "help",
        "language": "agnostic",
        "gloss": HELP_GLOSS,
        "prompt_vars": {},
        "goal_mode": False,
        "plan_mode": False,
        "notes_present": False,
        "source": {"source_kind": "built_in"},
        "built_in": True,
    }


__all__ = (
    "ACTION_NAME_REGEX",
    "MAX_REQUEST_BYTES",
    "SCHEMA_VERSION",
    "CatalogRequestError",
    "built_in_help_result",
    "decode_request_bytes",
    "error_result",
    "is_action_name",
    "load_action_catalog",
    "parse_selector",
    "process_request",
    "response_envelope",
    "validate_request",
)
