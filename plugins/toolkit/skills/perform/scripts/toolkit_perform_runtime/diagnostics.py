"""Structured diagnostics and source provenance for Perform."""


class CatalogRequestError(ValueError):
    """A catalog operation cannot safely fulfill the caller's request."""

    def __init__(self, status, message, selector=None, alternatives=None):
        """Store stable request status, explanation, and same-name alternatives."""
        super().__init__(message)
        self.status = status
        self.message = message
        self.selector = selector
        self.alternatives = list(alternatives or [])

    def to_dict(self):
        """Return JSON-ready error details."""
        return {
            "message": self.message,
            "selector": self.selector,
            "available_variants": self.alternatives,
        }


class Diagnostic:
    """One deterministic catalog or discovery issue."""

    __slots__ = (
        "code",
        "fatality",
        "filename_sort_key",
        "json_path",
        "message",
        "selector",
        "severity",
        "source_file",
        "source_order",
    )

    def __init__(
        self,
        severity,
        code,
        message,
        source_file=None,
        json_path=None,
        selector=None,
        fatality="nonfatal",
        source_order=-1,
        filename_sort_key=b"",
    ):
        """Store diagnostic content and its deterministic ordering metadata."""
        self.severity = severity
        self.code = code
        self.message = message
        self.source_file = source_file
        self.json_path = json_path
        self.selector = selector
        self.fatality = fatality
        self.source_order = source_order
        self.filename_sort_key = filename_sort_key

    @property
    def fatal(self):
        """Return whether this issue makes catalog precedence incomplete."""
        return self.fatality == "catalog_fatal"

    def sort_key(self):
        """Return the stable diagnostic ordering key."""
        return (
            self.source_order,
            self.filename_sort_key,
            (self.json_path or "").encode("utf-8"),
            self.code.encode("ascii"),
            self.message.encode("utf-8"),
        )

    def identity(self):
        """Return content used to deduplicate repeated dependent errors."""
        return (
            self.severity,
            self.code,
            self.message,
            self.source_file,
            self.json_path,
            self.selector,
            self.fatality,
        )

    def to_dict(self):
        """Return a stable JSON-ready representation."""
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "source_file": self.source_file,
            "json_path": self.json_path,
            "selector": self.selector,
            "fatality": self.fatality,
        }


class Provenance:
    """Origin of one effective action field."""

    __slots__ = ("json_path", "source_file", "source_kind", "source_order", "source_path")

    def __init__(self, source_kind, source_path, source_file, json_path, source_order):
        """Store normalized source identity and human-readable JSON location."""
        self.source_kind = source_kind
        self.source_path = source_path
        self.source_file = source_file
        self.json_path = json_path
        self.source_order = source_order

    def to_dict(self):
        """Return JSON-ready provenance."""
        return {
            "source_kind": self.source_kind,
            "source_path": self.source_path,
            "source_file": self.source_file,
            "json_path": self.json_path,
            "source_order": self.source_order,
        }


def json_pointer_component(value):
    """Escape one value for a JSON pointer component."""
    return value.replace("~", "~0").replace("/", "~1")


def sorted_unique_diagnostics(diagnostics):
    """Deduplicate diagnostics and return them in deterministic order."""
    unique = {}
    for diagnostic in diagnostics:
        key = diagnostic.identity()
        previous = unique.get(key)
        if previous is None or diagnostic.sort_key() < previous.sort_key():
            unique[key] = diagnostic
    return sorted(unique.values(), key=lambda diagnostic: diagnostic.sort_key())
