"""Release checksum command-line interface tests."""

import pytest

import la_dev_codex_plugins.release_checksums.cli as checksum_cli


def test_success_stdout_exactly_matches_persisted_utf8_lf_bytes(tmp_path, capfd):
    first = tmp_path / "first.bin"
    second = tmp_path / "caf\u00e9.bin"
    output = tmp_path / "SHA256SUMS"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    assert checksum_cli.main(["--output", str(output), str(first), str(second)]) == 0

    captured = capfd.readouterr()
    assert captured.out.encode("utf-8") == output.read_bytes()
    assert captured.err == ""
    assert output.read_bytes().endswith(b"\n")
    assert b"\r" not in output.read_bytes()


def test_expected_failure_has_prefix_no_stdout_or_traceback(tmp_path, capfd):
    output = tmp_path / "SHA256SUMS"
    missing = tmp_path / "missing.bin"

    assert checksum_cli.main(["--output", str(output), str(missing)]) == 1

    captured = capfd.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("la-dev-release-checksums: ")
    assert "Traceback" not in captured.err
    assert not output.exists()


def test_failure_path_is_backslash_escaped_on_one_line(tmp_path, capfd):
    output = tmp_path / "SHA256SUMS"
    invalid = tmp_path / "line\nreturn\rback\\slash.bin"

    assert checksum_cli.main(["--output", str(output), str(invalid)]) == 1

    captured = capfd.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1
    assert "line\\nreturn\\rback\\\\slash.bin" in captured.err


@pytest.mark.parametrize("arguments", [[], ["--output", "SHA256SUMS"], ["artifact.bin"]])
def test_usage_errors_exit_two_without_calling_library(arguments, monkeypatch):
    calls = []
    monkeypatch.setattr(checksum_cli.core, "write_sha256_manifest", lambda artifacts, output: calls.append((artifacts, output)))
    with pytest.raises(SystemExit) as caught:
        checksum_cli.main(arguments)
    assert caught.value.code == 2
    assert calls == []


@pytest.mark.parametrize("option", ["--help", "--version"])
def test_help_and_version_exit_zero(option, capsys):
    with pytest.raises(SystemExit) as caught:
        checksum_cli.main([option])
    assert caught.value.code == 0
    assert capsys.readouterr().out


def test_embedded_text_stream_without_buffer_uses_fallback(tmp_path, monkeypatch):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")

    class TextCapture:
        def __init__(self):
            self.text = ""

        def write(self, value):
            self.text += value

    capture = TextCapture()
    monkeypatch.setattr(checksum_cli.sys, "stdout", capture)
    assert checksum_cli.main(["--output", str(output), str(artifact)]) == 0
    assert capture.text.encode("utf-8") == output.read_bytes()


def test_binary_and_text_short_writes_are_completed(tmp_path, monkeypatch):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")

    class ShortWriter:
        def __init__(self):
            self.data = b""
            self.flushed = False

        def write(self, value):
            accepted = min(3, len(value))
            self.data += value[:accepted]
            return accepted

        def flush(self):
            self.flushed = True

    class BinaryStdout:
        def __init__(self):
            self.buffer = ShortWriter()

    binary = BinaryStdout()
    monkeypatch.setattr(checksum_cli.sys, "stdout", binary)
    assert checksum_cli.main(["--output", str(output), str(artifact)]) == 0
    assert binary.buffer.data == output.read_bytes()
    assert binary.buffer.flushed

    class ShortTextWriter:
        def __init__(self):
            self.text = ""
            self.flushed = False

        def write(self, value):
            accepted = min(4, len(value))
            self.text += value[:accepted]
            return accepted

        def flush(self):
            self.flushed = True

    text = ShortTextWriter()
    monkeypatch.setattr(checksum_cli.sys, "stdout", text)
    assert checksum_cli.main(["--output", str(output), str(artifact)]) == 0
    assert text.text.encode("utf-8") == output.read_bytes()
    assert text.flushed


@pytest.mark.parametrize("failure", [BrokenPipeError("closed consumer"), ValueError("closed stream")])
def test_stdout_write_failure_returns_one_without_removing_manifest(tmp_path, monkeypatch, capsys, failure):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")

    class FailingBuffer:
        def write(self, _value):
            raise failure

        def flush(self):
            raise AssertionError("flush must not follow a write failure")

    class FailingStdout:
        buffer = FailingBuffer()

    monkeypatch.setattr(checksum_cli.sys, "stdout", FailingStdout())
    assert checksum_cli.main(["--output", str(output), str(artifact)]) == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("la-dev-release-checksums: Could not write manifest to stdout:")
    assert "Traceback" not in captured.err
    assert output.read_bytes().endswith(b"  artifact.bin\n")


def test_stdout_flush_failure_can_leave_partial_stdout_but_preserves_manifest(tmp_path, monkeypatch, capsys):
    artifact = tmp_path / "artifact.bin"
    output = tmp_path / "SHA256SUMS"
    artifact.write_bytes(b"data")

    class FlushFailure:
        def __init__(self):
            self.data = b""

        def write(self, value):
            self.data += value
            return len(value)

        def flush(self):
            raise OSError("flush failed")

    class FailingStdout:
        def __init__(self):
            self.buffer = FlushFailure()

    stdout = FailingStdout()
    monkeypatch.setattr(checksum_cli.sys, "stdout", stdout)
    assert checksum_cli.main(["--output", str(output), str(artifact)]) == 1
    assert stdout.buffer.data == output.read_bytes()
    assert "flush failed" in capsys.readouterr().err
