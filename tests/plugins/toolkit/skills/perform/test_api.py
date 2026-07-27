"""Compact Perform API helper tests."""

import importlib
import io
import json

import pytest

api_module = importlib.import_module("toolkit_perform_runtime.api")
catalog_module = importlib.import_module("toolkit_perform_runtime.catalog")
diagnostics_module = importlib.import_module("toolkit_perform_runtime.diagnostics")
discovery_module = importlib.import_module("toolkit_perform_runtime.discovery")
cli_module = importlib.import_module("toolkit_perform_runtime.cli")


def test_public_request_error_has_domain_level_name():
    assert diagnostics_module.PerformRequestError.__name__ == "PerformRequestError"
    assert not hasattr(diagnostics_module, "CatalogRequestError")


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("invalid_arguments", 2),
        ("empty_rendered_prompt", 2),
        ("not_executable", 2),
        ("not_found", 2),
        ("fatal_catalog", 3),
        ("runtime_error", 4),
    ],
)
def test_error_exit_code_uses_documented_classes(code, expected):
    assert api_module.error_exit_code(code) == expected


def test_error_payload_omits_empty_alternatives_and_copies_nonempty_alternatives():
    assert api_module.error_payload("not_found", "Missing.") == {"error": {"code": "not_found", "message": "Missing."}}
    alternatives = ["test[python]"]
    payload = api_module.error_payload("not_found", "Missing.", alternatives)
    alternatives.append("test[rust]")
    assert payload == {"error": {"code": "not_found", "message": "Missing."}, "available_variants": ["test[python]"]}


def test_merge_response_payload_combines_copied_result_and_error():
    result = {"variants": []}
    error = diagnostics_module.PerformRequestError("not_found", "Missing.", alternatives=["test[python]"], diagnostics=["warning: Visible. (discovery)"])
    payload = api_module.merge_response_payload(result=result, error=error)
    result["later"] = True
    assert payload == {
        "variants": [],
        "error": {"code": "not_found", "message": "Missing."},
        "available_variants": ["test[python]"],
        "diagnostics": ["warning: Visible. (discovery)"],
    }


def test_compact_json_remains_a_string_serializer():
    rendered = api_module.compact_json({"value": "Unicode \u03bb"})
    assert isinstance(rendered, str)
    assert rendered == '{"value":"Unicode \u03bb"}'


def test_encode_json_writes_literal_unicode_and_escapes_lone_surrogates():
    value = {"text": "Unicode \u03bb " + chr(0xD800)}
    encoded = cli_module.encode_json(value)
    assert encoded.endswith(b"\n")
    assert encoded.count(b"\n") == 1
    assert "\u03bb".encode("utf-8") in encoded
    assert b"\\ud800" in encoded
    assert json.loads(encoded.decode("utf-8")) == value


def test_unicode_sort_key_preserves_normal_utf8_and_distinguishes_escape_text():
    assert diagnostics_module.unicode_sort_key("Unicode \u03bb") == "Unicode \u03bb".encode("utf-8")
    assert diagnostics_module.unicode_sort_key(chr(0xD800)) != diagnostics_module.unicode_sort_key("\\ud800")


def test_diagnostic_sorting_accepts_surrogates_in_paths_and_messages():
    surrogate = chr(0xD800)
    diagnostics = [
        diagnostics_module.Diagnostic("error", "second", "Message " + surrogate, json_path="/" + surrogate),
        diagnostics_module.Diagnostic("error", "first", "Ordinary", json_path="/ordinary"),
    ]
    assert len(diagnostics_module.sorted_unique_diagnostics(diagnostics)) == 2


def test_emit_json_supports_standard_text_and_binary_streams():
    text_stream = io.StringIO()
    binary_stream = io.BytesIO()
    cli_module.emit_json({"value": "Unicode \u03bb " + chr(0xD800)}, stream=text_stream)
    cli_module.emit_json({"value": "Unicode \u03bb " + chr(0xD800)}, stream=binary_stream)
    assert text_stream.getvalue().encode("utf-8") == binary_stream.getvalue()
    assert b"Unicode \xce\xbb \\ud800" in binary_stream.getvalue()


def test_emit_json_bypasses_restrictive_text_encoding_when_buffer_exists():
    binary_stream = io.BytesIO()
    text_stream = io.TextIOWrapper(binary_stream, encoding="ascii")
    cli_module.emit_json({"value": "Unicode \u03bb"}, stream=text_stream)
    assert "Unicode \u03bb".encode("utf-8") in binary_stream.getvalue()


def test_json_argument_parser_help_supports_text_streams():
    parser = cli_module.JsonArgumentParser(prog="test")
    stream = io.StringIO()
    parser.print_help(file=stream)
    response = json.loads(stream.getvalue())
    assert set(response) == {"help"}
    assert response["help"].startswith("usage: test")


def test_cli_runner_emits_one_success_result(monkeypatch):
    emitted = []
    monkeypatch.setattr(cli_module, "_write_encoded_json", lambda encoded: emitted.append(json.loads(encoded)))
    exit_code = cli_module.run_cli(lambda _context: cli_module.CliOutcome(result={"ok": True}))
    assert exit_code == 0
    assert emitted == [{"ok": True}]


def test_cli_runner_converts_request_and_runtime_errors_before_catalog_loading(monkeypatch):
    emitted = []
    monkeypatch.setattr(cli_module, "_write_encoded_json", lambda encoded: emitted.append(json.loads(encoded)))

    def request_error(_context):
        raise diagnostics_module.PerformRequestError("not_found", "Missing.")

    assert cli_module.run_cli(request_error) == 2
    assert emitted.pop() == {"error": {"code": "not_found", "message": "Missing."}}

    def runtime_error(_context):
        raise RuntimeError("Broken.")

    assert cli_module.run_cli(runtime_error) == 4
    assert emitted.pop() == {"error": {"code": "runtime_error", "message": "Broken."}}


def test_cli_runner_keeps_partial_results_and_catalog_diagnostics(monkeypatch):
    emitted = []
    monkeypatch.setattr(cli_module, "_write_encoded_json", lambda encoded: emitted.append(json.loads(encoded)))

    def command(context):
        diagnostics = [diagnostics_module.Diagnostic("warning", "warning", "Visible warning.")]
        context.catalog = catalog_module.ActionCatalog({}, diagnostics, discovery_module.explicit_discovery([]))
        error = diagnostics_module.PerformRequestError("fatal_catalog", "Incomplete.")
        return cli_module.CliOutcome(result={"variants": []}, error=error)

    assert cli_module.run_cli(command) == 3
    assert emitted == [
        {
            "variants": [],
            "error": {"code": "fatal_catalog", "message": "Incomplete."},
            "diagnostics": ["warning: Visible warning. (discovery)"],
        }
    ]


def test_cli_runner_replaces_unserializable_results_with_runtime_error(monkeypatch):
    emitted = []
    monkeypatch.setattr(cli_module, "_write_encoded_json", lambda encoded: emitted.append(json.loads(encoded)))
    exit_code = cli_module.run_cli(lambda _context: cli_module.CliOutcome(result={"bad": object()}))
    assert exit_code == 4
    assert set(emitted[0]) == {"error"}
    assert emitted[0]["error"]["code"] == "runtime_error"
    assert "not JSON serializable" in emitted[0]["error"]["message"]


def test_cli_runner_replaces_response_construction_failures(monkeypatch):
    emitted = []

    def fail_response(*_args, **_kwargs):
        raise RuntimeError("response failed")

    monkeypatch.setattr(cli_module.api, "merge_response_payload", fail_response)
    monkeypatch.setattr(cli_module, "_write_encoded_json", lambda encoded: emitted.append(json.loads(encoded)))
    assert cli_module.run_cli(lambda _context: cli_module.CliOutcome(result={"ok": True})) == 4
    assert emitted == [{"error": {"code": "runtime_error", "message": "response failed"}}]


def test_cli_runner_does_not_retry_failed_output_writes(monkeypatch):
    writes = []

    def fail_write(encoded):
        writes.append(encoded)
        raise OSError("stdout failed")

    monkeypatch.setattr(cli_module, "_write_encoded_json", fail_write)
    with pytest.raises(OSError, match="stdout failed"):
        cli_module.run_cli(lambda _context: cli_module.CliOutcome(result={"ok": True}))
    assert len(writes) == 1


def test_diagnostic_strings_deduplicate_flattened_collisions():
    diagnostics = [
        diagnostics_module.Diagnostic("warning", "first_code", "Same message.", source_file="/actions.json", selector="first[agnostic]"),
        diagnostics_module.Diagnostic("warning", "second_code", "Same message.", source_file="/actions.json", selector="second[agnostic]"),
    ]
    catalog = catalog_module.ActionCatalog({}, diagnostics, discovery_module.explicit_discovery([]))
    assert api_module.diagnostic_strings(catalog) == ["warning: Same message. (/actions.json)"]
