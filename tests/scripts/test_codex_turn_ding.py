"""Standalone completion-sound synthesis, notification, and playback contracts."""

import array
import contextlib
import importlib.util
import io
import json
import math
import os
import pathlib
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import wave

import pytest
import tomli

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "codex_turn_ding.py"


def create_state(path, records=()):
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("CREATE TABLE threads (id TEXT PRIMARY KEY, source TEXT, thread_source TEXT DEFAULT 'subagent')")
        connection.executemany("INSERT INTO threads (id, source) VALUES (?, ?)", records)
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def ding(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_SQLITE_HOME", str(tmp_path))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "unused-home"))
    spec = importlib.util.spec_from_file_location("codex_turn_ding", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def populated_state(ding):
    """Create recorded main threads for tests of completion filtering."""
    path = ding.sqlite_directory() / "state_5.sqlite"
    create_state(path, [(name, '"cli"') for name in ("chat-one", "chat-two", "chat")])
    return path


def backend(ding, name):
    return next(item for item in ding.PLAYER_BACKENDS if item.name == name)


def notification(thread_id="chat-one", **fields):
    return json.dumps(dict({"type": "agent-turn-complete", "thread-id": thread_id}, **fields))


@pytest.mark.parametrize(
    ("source", "allowed"),
    [
        ('"cli"', True),
        ('"vscode"', True),
        ('{"subagent":"review"}', True),
        ('{"subagent":{"thread_spawn":{"parent_thread_id":"parent","depth":1}}}', False),
        ('{"subagent":{"thread_spawn":{"parent_thread_id":"child","depth":5,"agent_role":"review"}}}', False),
        ('{"subagent":{"thread_spawn":{},"future":true},"extra":1}', False),
        ('{"subagent":{"future_kind":{}}}', True),
        ('{"subagent":{"thread_spawn":null}}', True),
        ('{"subagent":"thread_spawn"}', True),
        ('"future-client"', True),
        (None, True),
        ("not JSON", True),
        ("null", True),
        ("[]", True),
    ],
)
@pytest.mark.usefixtures("populated_state")
def test_completion_source_policy_preserves_review(ding, monkeypatch, capsys, source, allowed):
    with contextlib.closing(sqlite3.connect(str(ding.state_database(ding.sqlite_directory())))) as connection, connection:
        connection.execute("UPDATE threads SET source = ? WHERE id = ?", (source, "chat-one"))
    calls = []
    monkeypatch.setattr(ding, "play_tone", lambda *args: (calls.append(args) or True, []))
    assert ding.main([notification()]) == 0
    assert len(calls) == int(allowed)
    assert capsys.readouterr() == ("", "")


@pytest.mark.usefixtures("populated_state")
def test_absent_record_retries_then_stays_silent(ding, monkeypatch, capsys):
    delays = []
    monkeypatch.setattr(ding.time, "sleep", delays.append)
    monkeypatch.setattr(ding, "play_tone", unexpected_playback)
    assert ding.main([notification("ephemeral")]) == 0
    assert delays == [0.05, 0.05]
    assert capsys.readouterr() == ("", "")


@pytest.mark.usefixtures("populated_state")
def test_retry_observes_newly_committed_wal_record(ding, monkeypatch):
    writer = sqlite3.connect(str(ding.state_database(ding.sqlite_directory())))
    try:
        writer.execute("PRAGMA journal_mode=WAL")

        def persist(_delay):
            writer.execute("INSERT INTO threads (id, source) VALUES (?, ?)", ("persisting", '"cli"'))
            writer.commit()

        monkeypatch.setattr(ding.time, "sleep", persist)
        assert ding.notification_note(notification("persisting")) == ding.note_index("persisting")
        # A second connection's committed WAL data must also be visible on the first lookup.
        assert ding.notification_note(notification("persisting")) == ding.note_index("persisting")
    finally:
        writer.close()


@pytest.mark.parametrize("failure", ["missing-directory", "missing-database", "corrupt", "schema", "permission", "locked"])
def test_lookup_errors_keep_ding_without_creating_database(ding, tmp_path, monkeypatch, capsys, failure):
    directory = tmp_path / "lookup"
    if failure != "missing-directory":
        directory.mkdir()
    path = directory / "state_12.sqlite"
    lock = None
    if failure == "corrupt":
        path.write_bytes(b"not a database")
    elif failure in ("schema", "permission", "locked"):
        create_state(path, [("chat-one", '"cli"')])
        if failure == "schema":
            with contextlib.closing(sqlite3.connect(str(path))) as connection, connection:
                connection.execute("DROP TABLE threads")
        elif failure == "permission":

            def deny(_path):
                raise PermissionError("denied")

            monkeypatch.setattr(ding, "open_state_database", deny)
        else:
            lock = sqlite3.connect(str(path))
            lock.execute("BEGIN EXCLUSIVE")
    before = sorted(directory.iterdir()) if directory.exists() else []
    calls = []
    monkeypatch.setattr(ding, "play_tone", lambda *args: (calls.append(args) or True, []))
    try:
        assert ding.main(["--sqlite-home", str(directory), notification()]) == 0
    finally:
        if lock is not None:
            lock.close()
    assert calls == [(ding.note_index("chat-one"), ding.DEFAULT_VOLUME)]
    assert (sorted(directory.iterdir()) if directory.exists() else []) == before
    assert directory.exists() == (failure != "missing-directory")
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("error_type", [OSError, ValueError])
def test_state_resolution_errors_retain_alerts_and_diagnostics(ding, monkeypatch, capsys, error_type):
    def fail_resolution(_override):
        raise error_type("State directory unavailable")

    monkeypatch.setattr(ding, "sqlite_directory", fail_resolution)
    calls = []
    monkeypatch.setattr(ding, "play_tone", lambda *args: (calls.append(args) or True, []))
    assert ding.main([notification()]) == 0
    assert calls == [(ding.note_index("chat-one"), ding.DEFAULT_VOLUME)]
    assert capsys.readouterr() == ("", "")
    monkeypatch.setattr(ding, "available_players", list)
    assert ding.main(["--diagnose"]) == 1
    captured = capsys.readouterr()
    assert captured.out
    assert captured.err == ""
    assert len(calls) == 1


@pytest.mark.parametrize("path_source", ["CODEX_SQLITE_HOME", "CODEX_HOME", "explicit"])
def test_deleted_working_directory_retains_completion(ding, tmp_path, path_source):
    vanished = tmp_path / "vanished"
    vanished.mkdir()
    environment = dict(os.environ, CODEX_HOME=str(tmp_path), CODEX_SQLITE_HOME="")
    if path_source != "explicit":
        environment[path_source] = "relative-state"
    program = """import importlib.util, json, os, sys
spec = importlib.util.spec_from_file_location('ding_deleted_cwd', sys.argv[1])
ding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ding)
calls = []
ding.play_tone = lambda *args: (calls.append(args) or True, [])
os.chdir(sys.argv[2])
os.rmdir(sys.argv[2])
arguments = ['--sqlite-home', 'relative-state'] if sys.argv[3] == 'explicit' else []
status = ding.main(arguments + [json.dumps({'type': 'agent-turn-complete', 'thread-id': 'chat-one'})])
print(json.dumps([status, calls]))
"""
    result = subprocess.run([sys.executable, "-I", "-c", program, str(SCRIPT), str(vanished), path_source], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, check=True)
    assert json.loads(result.stdout) == [0, [[ding.note_index("chat-one"), ding.DEFAULT_VOLUME]]]
    assert result.stderr == b""


@pytest.mark.parametrize("thread", ["chat-one", "absent"])
def test_muted_completions_skip_state_access_and_retries(ding, monkeypatch, capsys, thread):
    monkeypatch.setattr(ding, "sqlite_directory", unexpected_playback)
    monkeypatch.setattr(ding, "open_state_database", unexpected_playback)
    monkeypatch.setattr(ding.time, "sleep", unexpected_playback)
    monkeypatch.setattr(ding, "play_tone", unexpected_playback)
    assert ding.main(["--volume", "0", notification(thread)]) == 0
    assert capsys.readouterr() == ("", "")


def test_zero_volume_preserves_utility_modes(ding, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(ding, "play_tone", lambda *args: (calls.append(args) or True, []))
    monkeypatch.setattr(ding.time, "sleep", lambda _delay: None)
    assert ding.main(["--preview", "--volume", "0"]) == 0
    assert calls == [(index, 0) for index in range(len(ding.NOTE_NAMES))]
    assert capsys.readouterr().out
    directories = []
    monkeypatch.setattr(ding, "diagnose_state", directories.append)
    monkeypatch.setattr(ding, "available_players", list)
    assert ding.main(["--diagnose", "--volume", "0", "--sqlite-home", "state-directory"]) == 1
    assert directories == ["state-directory"]
    assert capsys.readouterr().out
    for mode, parse in [("--print-config", tomli.loads), ("--print-hooks", json.loads)]:
        assert ding.main([mode, "--volume", "0"]) == 0
        assert parse(capsys.readouterr().out)


def test_newest_database_is_numeric_and_never_falls_back(ding, tmp_path):
    create_state(tmp_path / "state_9.sqlite", [("old", '"cli"')])
    create_state(tmp_path / "state_10.sqlite")
    (tmp_path / "state_99.sqlite.backup").write_bytes(b"ignored")
    (tmp_path / "logs_100.sqlite").write_bytes(b"ignored")
    assert ding.state_database(tmp_path).name == "state_10.sqlite"
    assert ding.notification_note(notification("old")) is None
    (tmp_path / "state_10.sqlite").write_bytes(b"incompatible newest database")
    assert ding.notification_note(notification("old")) == ding.note_index("old")


def test_sqlite_directory_precedence(ding, tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setenv("CODEX_SQLITE_HOME", str(tmp_path / "sqlite"))
    assert ding.sqlite_directory(str(tmp_path / "explicit")) == tmp_path / "explicit"
    assert ding.sqlite_directory() == tmp_path / "sqlite"
    monkeypatch.setenv("CODEX_SQLITE_HOME", " \t")
    assert ding.sqlite_directory() == tmp_path / "codex"
    monkeypatch.setenv("CODEX_HOME", " ")
    monkeypatch.setattr(ding.pathlib.Path, "home", lambda: tmp_path)
    assert ding.sqlite_directory() == tmp_path / ".codex"
    monkeypatch.chdir(tmp_path)
    assert ding.sqlite_directory("relative") == tmp_path / "relative"


@pytest.mark.parametrize("kind", ["fifo", "directory", "dangling-link", "fifo-link"])
def test_nonregular_newest_database_keeps_sound_without_fallback(ding, tmp_path, monkeypatch, capsys, kind):
    create_state(tmp_path / "state_4.sqlite")
    newest = tmp_path / "state_5.sqlite"
    if kind == "fifo":
        os.mkfifo(str(newest))
    elif kind == "directory":
        newest.mkdir()
    else:
        target = tmp_path / "target"
        if kind == "fifo-link":
            os.mkfifo(str(target))
        newest.symlink_to(target)
    # Bound subprocesses so a regression cannot hang the test runner on FIFO open.
    for arguments in (["--diagnose"], ["--volume", "0", notification()]):
        result = subprocess.run([sys.executable, str(SCRIPT), "--sqlite-home", str(tmp_path), *arguments], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, check=False)
        assert result.returncode in ((0, 1) if arguments == ["--diagnose"] else (0,))
        assert result.stderr == b""
    assert ding.state_database(tmp_path) == newest
    with pytest.raises(OSError, match=r".+"):
        ding.open_state_database(newest)
    assert ding.notification_note(notification()) == ding.note_index("chat-one")
    monkeypatch.setattr(ding, "available_players", lambda: [(backend(ding, "afplay"), "/afplay")])
    assert ding.main(["--diagnose"]) == 0
    assert str(newest) in capsys.readouterr().out


def test_regular_database_symlink_is_supported(ding, tmp_path):
    target = tmp_path / "target.sqlite"
    create_state(target, [("chat-one", '"cli"'), ("child", '{"subagent":{"thread_spawn":{}}}')])
    (tmp_path / "state_5.sqlite").symlink_to(target)
    assert ding.notification_note(notification()) == ding.note_index("chat-one")
    assert ding.notification_note(notification("child")) is None
    assert ding.notification_note(notification("absent")) is None


@pytest.mark.parametrize("variable", ["CODEX_SQLITE_HOME", "CODEX_HOME"])
@pytest.mark.parametrize("directory_name", [" state", "state ", "\tstate\t"])
def test_environment_directory_preserves_whitespace(ding, tmp_path, monkeypatch, variable, directory_name):
    monkeypatch.delenv("CODEX_SQLITE_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    directory = tmp_path / directory_name
    directory.mkdir()
    create_state(directory / "state_5.sqlite", [("main", '"cli"'), ("child", '{"subagent":{"thread_spawn":{}}}')])
    trimmed = tmp_path / directory_name.strip()
    trimmed.mkdir()
    create_state(trimmed / "state_5.sqlite", [("child", '"cli"')])
    monkeypatch.setenv(variable, directory_name)
    assert ding.sqlite_directory() == directory
    assert ding.notification_note(notification("main")) == ding.note_index("main")
    assert ding.notification_note(notification("child")) is None


def test_explicit_directory_round_trips_and_escapes_uri(ding, tmp_path, monkeypatch):
    directory = tmp_path / "space 'quote' # ? % \u00e9"
    directory.mkdir()
    create_state(directory / "state_12.sqlite", [("chat-one", '{"subagent":"review"}')])
    assert ding.notification_note(notification(), str(directory)) == ding.note_index("chat-one")
    monkeypatch.chdir(tmp_path)
    command = tomli.loads(ding.configuration(0.5, directory.name))["notify"]
    assert command[command.index("--sqlite-home") + 1] == str(directory)
    assert subprocess.run([*command, notification("ephemeral")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout == b""


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Fake paplay exercises Linux playback")
def test_generated_completion_command_filters_background_and_preserves_review(ding, tmp_path):
    directory = tmp_path / "state # ? % \u00e9"
    directory.mkdir()
    create_state(directory / "state_12.sqlite", [("main", '"cli"'), ("review", '{"subagent":"review"}'), ("child", '{"subagent":{"thread_spawn":{"depth":2}}}')])
    player = tmp_path / "paplay"
    marker = tmp_path / "completion-played"
    player.write_text("#!/bin/sh\nprintf x >> {}\n".format(shlex.quote(str(marker))))
    player.chmod(0o700)
    command = tomli.loads(ding.configuration(0.5, str(directory)))["notify"]
    environment = dict(os.environ, PATH=str(tmp_path))
    for name in ("child", "ephemeral", "main", "review"):
        result = subprocess.run([*command, notification(name)], env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        assert result.stdout == result.stderr == b""
    assert marker.read_text() == "xx"


@pytest.mark.parametrize("record", [None, '{"subagent":{"thread_spawn":{"depth":3}}}'])
@pytest.mark.usefixtures("populated_state")
def test_background_attention_hooks_bypass_completion_filter(ding, monkeypatch, record):
    with contextlib.closing(sqlite3.connect(str(ding.state_database(ding.sqlite_directory())))) as connection, connection:
        connection.execute("DELETE FROM threads WHERE id = ?", ("chat-one",))
        if record is not None:
            connection.execute("INSERT INTO threads (id, source) VALUES (?, ?)", ("chat-one", record))
    monkeypatch.setattr(ding.time, "sleep", lambda _delay: None)
    assert ding.notification_note(notification()) is None
    monkeypatch.setattr(ding, "completion_allowed", unexpected_playback)
    calls = []
    monkeypatch.setattr(ding, "play_tone", lambda *args: (calls.append(args) or True, []))
    for event in [
        {"hook_event_name": "PermissionRequest"},
        {"hook_event_name": "PreToolUse", "tool_name": "request_user_input"},
        {"hook_event_name": "PreToolUse", "tool_name": "request_user_input_async"},
    ]:
        monkeypatch.setattr(ding.sys, "stdin", io.StringIO(json.dumps(dict(event, session_id="chat-one"))))
        assert ding.main(["--hook"]) == 0
    assert calls == [(ding.note_index("chat-one"), ding.DEFAULT_VOLUME)] * 3


@pytest.mark.usefixtures("populated_state")
def test_state_connections_are_read_only_and_closed(ding):
    path = ding.state_database(ding.sqlite_directory())
    connection = ding.open_state_database(path)
    try:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM threads")
    finally:
        connection.close()
    assert ding.completion_allowed("chat-one", ding.sqlite_directory())
    with contextlib.closing(sqlite3.connect(str(path), timeout=0)) as writer, writer:
        writer.execute("BEGIN EXCLUSIVE")
        writer.execute("UPDATE threads SET source = source")


@pytest.mark.usefixtures("populated_state")
def test_diagnose_reports_schema_without_conversation_content(ding, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ding, "available_players", lambda: [(backend(ding, "afplay"), "/afplay")])
    assert ding.main(["--diagnose"]) == 0
    output = capsys.readouterr().out
    assert str(tmp_path / "state_5.sqlite") in output
    assert "schema available" in output
    assert "chat-one" not in output
    assert ding.main(["--diagnose", "--sqlite-home", str(tmp_path / "missing")]) == 0
    assert "filtering unavailable" in capsys.readouterr().out


def unexpected_playback(*_args):
    raise AssertionError("Unexpected playback")


@pytest.mark.usefixtures("populated_state")
def test_pitch_is_stable_across_processes_and_turns(ding):
    assert ding.note_index("chat-one") == 11
    assert ding.note_index("chat-two") == 1
    values = []
    for seed in ("1", "42"):
        environment = dict(os.environ, PYTHONHASHSEED=seed)
        result = subprocess.run(
            [sys.executable, "-I", "-c", "import runpy,sys; print(runpy.run_path(sys.argv[1])['note_index']('chat-one'))", str(SCRIPT)], env=environment, stdout=subprocess.PIPE, check=True
        )
        values.append(int(result.stdout))
    assert values == [ding.note_index("chat-one")] * 2
    assert ding.notification_note(notification(**{"turn-id": "first", "cwd": "/one"})) == ding.notification_note(notification(**{"turn-id": "resumed", "cwd": "/two"}))
    assert {ding.note_index("chat-{}".format(index)) for index in range(200)} == set(range(13))
    assert ding.frequency_for_note(0) == pytest.approx(261.6255653)
    assert ding.frequency_for_note(12) == pytest.approx(523.2511306)


@pytest.mark.parametrize(
    "event",
    [
        {"hook_event_name": "PermissionRequest", "tool_name": "Bash"},
        *({"hook_event_name": "PreToolUse", "tool_name": prefix + name} for prefix in ("", "functions", "functions.", "functions_") for name in ("request_user_input", "request_user_input_async")),
    ],
)
@pytest.mark.usefixtures("populated_state")
def test_attention_hooks_preserve_pitch_and_each_event_plays(ding, monkeypatch, capsys, event):
    payload = json.dumps(dict(event, session_id="chat-one"))
    calls = []
    monkeypatch.setattr(ding, "play_tone", lambda *args: (calls.append(args) or True, []))
    for _attempt in range(2):
        monkeypatch.setattr(ding.sys, "stdin", io.StringIO(payload))
        assert ding.main(["--hook"]) == 0
    assert ding.main([notification()]) == 0
    assert calls == [(ding.note_index("chat-one"), 0.85)] * 3
    assert ding.hook_note(payload) == ding.notification_note(notification())
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    "event",
    [
        None,
        [],
        {},
        {"hook_event_name": "Stop", "session_id": "chat"},
        {"hook_event_name": "PreToolUse", "tool_name": "exec_command", "session_id": "chat"},
        {"hook_event_name": "PreToolUse", "tool_name": "fake_request_user_input", "session_id": "chat"},
        *({"hook_event_name": "PermissionRequest", "session_id": value} for value in (None, 42, " ", "\ud800")),
    ],
)
def test_unrelated_or_invalid_hooks_are_quiet(ding, monkeypatch, capsys, event):
    monkeypatch.setattr(ding.sys, "stdin", io.StringIO(json.dumps(event)))
    monkeypatch.setattr(ding, "play_tone", unexpected_playback)
    assert ding.main(["--hook"]) == 0
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("payload", ["", "{", "not JSON"])
def test_malformed_hook_input_is_quiet(ding, monkeypatch, payload):
    monkeypatch.setattr(ding.sys, "stdin", io.StringIO(payload))
    assert ding.main(["--hook"]) == 0


@pytest.mark.parametrize(
    ("tool", "accepted"),
    [(prefix + name, True) for prefix in ("", "functions", "functions.", "functions_") for name in ("request_user_input", "request_user_input_async")]
    + [(name, False) for name in ("", "exec_command", "fake_request_user_input", "request_user_input_extra", "request_user_input\n", "functions..request_user_input", " request_user_input")],
)
def test_generated_and_runtime_question_matchers_agree(ding, tool, accepted):
    matcher = json.loads(ding.hook_configuration(ding.DEFAULT_VOLUME))["hooks"]["PreToolUse"][0]["matcher"]
    event = json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "session_id": "chat"})
    assert (re.fullmatch(matcher, tool) is not None) == accepted
    assert (ding.hook_note(event) is not None) == accepted


@pytest.mark.parametrize("volume", [0.0, 0.5, 0.85, 1.0])
def test_generated_hook_commands_work_with_literal_install_paths(tmp_path, volume):
    installed = tmp_path / "space 'quote' $literal `text` \u00e9" / "ding.py"
    installed.parent.mkdir()
    shutil.copyfile(SCRIPT, installed)
    output = subprocess.run([sys.executable, "-I", str(installed), "--print-hooks", "--volume", str(volume)], stdout=subprocess.PIPE, check=True)
    assert output.stdout.isascii()
    hooks = json.loads(output.stdout)["hooks"]
    assert set(hooks) == {"PermissionRequest", "PreToolUse"}
    matcher = hooks["PreToolUse"][0]["matcher"]
    assert re.fullmatch(matcher, "request_user_input")
    assert re.fullmatch(matcher, "functions.request_user_input_async")
    assert not re.fullmatch(matcher, "exec_command")
    handler = hooks["PermissionRequest"][0]["hooks"][0]
    assert handler["async"] is True
    command = shlex.split(handler["command"])
    expected = [str(pathlib.Path(sys.executable).absolute()), "-I", str(installed), "--hook"]
    if volume != 0.85:
        expected.extend(["--volume", str(volume)])
    assert command == expected
    # Execute the generated shell command with an unrelated event: no audio or shell expansion.
    result = subprocess.run(["/bin/sh", "-c", handler["command"]], input=b'{"hook_event_name":"Stop","session_id":"chat"}', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert result.stdout == result.stderr == b""


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Fake paplay exercises Linux playback")
def test_hook_stdin_plays_via_generated_command(ding, tmp_path):
    player = tmp_path / "paplay"
    marker = tmp_path / "played"
    player.write_text("#!/bin/sh\nprintf x >> {}\n".format(shlex.quote(str(marker))))
    player.chmod(0o700)
    environment = dict(os.environ, PATH=str(tmp_path))
    handler = json.loads(ding.hook_configuration(0.5))["hooks"]["PermissionRequest"][0]["hooks"][0]
    events = [{"hook_event_name": "PermissionRequest", "session_id": "chat"}, {"hook_event_name": "PreToolUse", "session_id": "chat", "tool_name": "request_user_input_async"}]
    for event in events:
        result = subprocess.run(["/bin/sh", "-c", handler["command"]], input=json.dumps(event).encode(), env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        assert result.stdout == result.stderr == b""
    assert marker.read_text() == "xx"


def test_hook_volume_zero_does_not_play(ding, monkeypatch):
    monkeypatch.setattr(ding.sys, "stdin", io.StringIO(json.dumps({"hook_event_name": "PermissionRequest", "session_id": "chat"})))
    monkeypatch.setattr(ding, "play_tone", unexpected_playback)
    assert ding.main(["--hook", "--volume", "0"]) == 0


@pytest.mark.parametrize(
    "payload",
    [
        "",
        "{",
        "null",
        "[]",
        "42",
        '"text"',
        '{"type":"approval-requested","thread-id":"chat"}',
        '{"type":"agent-turn-complete"}',
        notification(None),
        notification(42),
        notification(" "),
        notification("\ud800"),
    ],
)
def test_ignored_notifications_do_not_play(ding, monkeypatch, capsys, payload):
    def unexpected_playback(*_args):
        raise AssertionError("Ignored notification played audio")

    monkeypatch.setattr(ding, "play_tone", unexpected_playback)
    assert ding.main([payload]) == 0
    assert capsys.readouterr() == ("", "")


@pytest.mark.usefixtures("populated_state")
def test_notification_argument_is_data_and_volume_zero_silences(ding, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(ding, "play_tone", lambda *args: (calls.append(args) or True, []))
    thread = 'chat\n"$(touch /tmp/never-run);`echo unsafe`\u00e9'
    with contextlib.closing(sqlite3.connect(str(ding.state_database(ding.sqlite_directory())))) as connection, connection:
        connection.execute("INSERT INTO threads (id, source) VALUES (?, ?)", (thread, '"cli"'))
    assert ding.main(["--volume", "0.5", notification(thread)]) == 0
    assert calls == [(ding.note_index(thread), 0.5)]
    assert ding.main(["--volume", "0", notification(thread)]) == 0
    assert len(calls) == 1
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("volume", ["-0.1", "1.1", "nan", "inf", "nonsense"])
def test_invalid_volume_is_a_usage_error(ding, volume):
    with pytest.raises(SystemExit) as error:
        ding.main(["--volume", volume, "--print-config"])
    assert error.value.code == 2


@pytest.mark.parametrize("index", [0, 6, 12])
@pytest.mark.parametrize("volume", [0, 0.85, 1])
def test_wav_has_expected_format_envelope_and_pitch(ding, tmp_path, index, volume):
    path = tmp_path / "tone.wav"
    ding.write_tone(path, index, volume)
    with wave.open(str(path), "rb") as sound:
        assert (sound.getnchannels(), sound.getsampwidth(), sound.getframerate()) == (1, 2, 44100)
        assert sound.getnframes() == round(44100 * 0.25) + round(44100 * 1.1)
        samples = array.array("h", sound.readframes(sound.getnframes()))
    if sys.byteorder != "little":
        samples.byteswap()
    lead = round(44100 * 0.25)
    assert not any(samples[:lead])
    assert max(abs(sample) for sample in samples) <= 32767 * volume
    assert samples[lead] == 0
    assert abs(samples[-1]) <= 1
    if volume:
        frequency = ding.frequency_for_note(index)
        segment = samples[lead : lead + round(44100 * 0.20)]

        def power_at(hz):
            real = sum(sample * math.cos(2 * math.pi * hz * offset / 44100) for offset, sample in enumerate(segment))
            imaginary = sum(sample * math.sin(2 * math.pi * hz * offset / 44100) for offset, sample in enumerate(segment))
            return real * real + imaginary * imaginary

        assert power_at(frequency) > 10 * power_at(frequency * 1.05)
        assert power_at(frequency) > 10 * power_at(frequency * 0.95)
        assert ding.envelope_at(0.10) == ding.envelope_at(0.20) == 1
        assert 0 < ding.envelope_at(0.8) < ding.envelope_at(0.4) < 1


@pytest.mark.parametrize(("platform", "expected"), [("linux", ["paplay", "pw-play", "aplay", "ffplay", "play"]), ("darwin", ["afplay", "ffplay", "play"]), ("win32", [])])
def test_player_discovery_and_order(ding, monkeypatch, platform, expected):
    monkeypatch.setattr(ding.sys, "platform", platform)
    monkeypatch.setattr(ding.shutil, "which", lambda name: "/tools/" + name)
    monkeypatch.setattr(ding.os, "access", lambda *_args: True)
    players = ding.available_players()
    assert [item.name for item, _path in players] == expected
    if platform == "darwin":
        assert players[0][1] == "/usr/bin/afplay"
    monkeypatch.setattr(ding.shutil, "which", lambda _name: None)
    monkeypatch.setattr(ding.os, "access", lambda *_args: False)
    assert ding.available_players() == []


@pytest.mark.parametrize(
    ("name", "options"),
    [("afplay", []), ("paplay", ["--client-name=Codex ding"]), ("pw-play", []), ("aplay", ["-q"]), ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "error"]), ("play", ["-q"])],
)
def test_player_commands_preserve_literal_paths(ding, name, options):
    path = pathlib.Path('/tmp/with spaces/"$(unsafe)\u00e9.wav')
    assert ding.player_command(backend(ding, name), "/tools/" + name, path) == ["/tools/" + name, *options, str(path)]


@pytest.mark.parametrize("failure", ["status", "timeout", "oserror", "success"])
def test_playback_fallback_and_cleanup(ding, monkeypatch, failure):
    monkeypatch.setattr(ding, "available_players", lambda: [(backend(ding, "paplay"), "/paplay"), (backend(ding, "aplay"), "/aplay")])
    paths = []

    def run(command, **kwargs):
        path = pathlib.Path(command[-1])
        assert path.is_file()
        paths.append(path)
        assert kwargs["stdin"] == kwargs["stdout"] == kwargs["stderr"] == subprocess.DEVNULL
        assert 0 < kwargs["timeout"] <= 3
        assert not kwargs.get("shell")
        if len(paths) == 1:
            if failure == "timeout":
                raise subprocess.TimeoutExpired(command, 3)
            if failure == "oserror":
                raise OSError("player disappeared")
            if failure == "status":
                return subprocess.CompletedProcess(command, 1)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(ding.subprocess, "run", run)
    success, failures = ding.play_tone(6, 0.85)
    assert success
    assert len(paths) == (1 if failure == "success" else 2)
    assert bool(failures) == (failure != "success")
    assert all(not path.parent.exists() for path in paths)


def test_playback_budget_and_failed_hook_are_quiet(ding, monkeypatch, capsys):
    monkeypatch.setattr(ding, "available_players", lambda: [(backend(ding, name), "/" + name) for name in ("paplay", "pw-play", "aplay", "ffplay", "play")])
    clock = iter([0, 0, 3, 6, 8])
    monkeypatch.setattr(ding.time, "monotonic", lambda: next(clock))
    timeouts = []
    paths = []

    def fail(command, **kwargs):
        timeouts.append(kwargs["timeout"])
        paths.append(pathlib.Path(command[-1]))
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(ding.subprocess, "run", fail)
    assert ding.main([notification()]) == 0
    assert timeouts == [3, 3, 2]
    assert all(not path.parent.exists() for path in paths)
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("name", ["paplay", "ffplay"])
def test_real_player_timeout_and_temporary_cleanup(ding, monkeypatch, name):
    monkeypatch.setattr(ding, "available_players", lambda: [(backend(ding, name), sys.executable)])
    monkeypatch.setattr(ding, "ATTEMPT_SECONDS", 0.05)
    paths = []

    def command(_name, executable, path):
        paths.append(path)
        return [executable, "-I", "-c", "import time; time.sleep(10)"]

    monkeypatch.setattr(ding, "player_command", command)
    success, failures = ding.play_tone(0, 0.85)
    assert not success
    assert failures
    assert not paths[0].parent.exists()


def test_synthesis_failure_cleans_up_temporary_directory(ding, monkeypatch, capsys):
    monkeypatch.setattr(ding, "available_players", lambda: [(backend(ding, "paplay"), "/paplay")])
    paths = []

    def fail(path, _index, _volume):
        paths.append(path)
        path.write_bytes(b"incomplete")
        raise OSError("write failed")

    monkeypatch.setattr(ding, "write_tone", fail)
    assert ding.main([notification()]) == 0
    assert not paths[0].parent.exists()
    assert capsys.readouterr() == ("", "")


def test_missing_player_and_unwritable_temp_directory(ding, monkeypatch, capsys):
    monkeypatch.setattr(ding, "available_players", list)
    assert ding.main([notification()]) == 0
    assert capsys.readouterr() == ("", "")
    assert ding.main(["--diagnose"]) == 1
    assert capsys.readouterr().out
    assert ding.main(["--preview"]) == 1
    assert capsys.readouterr().err
    monkeypatch.setattr(ding, "available_players", lambda: [(backend(ding, "paplay"), "/paplay")])

    def deny(**_kwargs):
        raise PermissionError("temporary files denied")

    monkeypatch.setattr(ding.tempfile, "TemporaryDirectory", deny)
    assert ding.main([notification()]) == 0
    assert capsys.readouterr() == ("", "")
    assert ding.main(["--preview"]) == 1
    assert capsys.readouterr().err


def test_preview_and_diagnosis(ding, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(ding, "play_tone", lambda *args: (calls.append(args) or True, []))
    monkeypatch.setattr(ding.time, "sleep", lambda _seconds: None)
    assert ding.main(["--preview"]) == 0
    assert calls == [(index, 0.85) for index in range(13)]
    assert len(capsys.readouterr().out.splitlines()) == 13
    monkeypatch.setattr(ding, "available_players", lambda: [(backend(ding, "afplay"), "/usr/bin/afplay")])
    assert ding.main(["--diagnose"]) == 0
    assert "/usr/bin/afplay" in capsys.readouterr().out
    assert len(calls) == 13


@pytest.mark.parametrize("directory", ['space and "quote" \u00e9', "emoji-\U0001f514", "cjk-\U00020000", "back\\slash\t\n\r\x01\x7f"])
@pytest.mark.parametrize("volume", [0.0, 0.85, 0.5, 1.0])
def test_generated_configuration_works_after_copying(ding, tmp_path, capsys, directory, volume):
    installed = tmp_path / directory / "ding.py"
    installed.parent.mkdir()
    shutil.copyfile(SCRIPT, installed)
    result = subprocess.run([sys.executable, "-I", str(installed), "--print-config", "--volume", str(volume)], stdout=subprocess.PIPE, check=True)
    command = tomli.loads(result.stdout.decode())["notify"]
    expected = [str(pathlib.Path(sys.executable).absolute()), "-I", str(installed.resolve())]
    if volume != ding.DEFAULT_VOLUME:
        expected.extend(["--volume", str(volume)])
    assert command == expected
    assert result.stdout.isascii()
    completed = subprocess.run([*command, notification(type="ignored")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert completed.stdout == completed.stderr == b""
    assert ding.main(["--print-config"]) == 0
    assert tomli.loads(capsys.readouterr().out)["notify"] == [str(pathlib.Path(sys.executable).absolute()), "-I", str(SCRIPT)]


def test_toml_string_round_trips_scalar_characters(ding):
    value = "".join(chr(code) for code in range(128)) + "\u00e9\u2028\uffff\U0001f514\U00020000\U0010ffff"
    entry = "value = " + ding.toml_string(value)
    assert entry.isascii()
    assert tomli.loads(entry)["value"] == value


@pytest.mark.parametrize("interpreter", ["/tools/\U0001f514/python3", '/tools/quote"back\\slash\t\u00e9/python3'])
@pytest.mark.parametrize("mode", ["--print-config", "--print-hooks"])
def test_configuration_preserves_interpreter_path(ding, monkeypatch, capsys, interpreter, mode):
    monkeypatch.setattr(ding.sys, "executable", interpreter)
    assert ding.main([mode]) == 0
    output = capsys.readouterr().out
    if mode == "--print-config":
        command = tomli.loads(output)["notify"]
        assert command == [interpreter, "-I", str(SCRIPT)]
    else:
        command = shlex.split(json.loads(output)["hooks"]["PermissionRequest"][0]["hooks"][0]["command"])
        assert command == [interpreter, "-I", str(SCRIPT), "--hook"]


@pytest.mark.parametrize("mode", ["--print-config", "--print-hooks"])
def test_sqlite_override_is_generated_only_for_completions(ding, tmp_path, capsys, mode):
    directory = str(tmp_path / "state directory")
    assert ding.main([mode, "--sqlite-home", directory, "--volume", "0.5"]) == 0
    output = capsys.readouterr().out
    base = [str(pathlib.Path(sys.executable).absolute()), "-I", str(SCRIPT)]
    if mode == "--print-config":
        command = tomli.loads(output)["notify"]
        assert command == [*base, "--sqlite-home", directory, "--volume", "0.5"]
    else:
        command = shlex.split(json.loads(output)["hooks"]["PermissionRequest"][0]["hooks"][0]["command"])
        assert command == [*base, "--hook", "--volume", "0.5"]


@pytest.mark.parametrize("surrogate_codepoint", [0xD800, 0xDFFF, 0xDCFF])
@pytest.mark.parametrize("path_source", ["script", "interpreter"])
@pytest.mark.parametrize("mode", ["--print-config", "--print-hooks"])
def test_unrepresentable_configuration_fails_cleanly(ding, monkeypatch, capsys, surrogate_codepoint, path_source, mode):
    surrogate = chr(surrogate_codepoint)
    if path_source == "script":
        monkeypatch.setattr(ding, "__file__", "/tmp/" + surrogate + "/ding.py")
    else:
        monkeypatch.setattr(ding.sys, "executable", "/tmp/" + surrogate + "/python3")
    assert ding.main([mode]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    ("returncode", "diagnostic", "fallback"),
    [
        (0, b"No more combinations to try, audio open failed", True),
        (0, b"Failed to open file 'ding.wav' or configure filtergraph", True),
        (0, b"Could not initialize SDL - audio unavailable", True),
        (0, b"SDL_OpenAudio (1 channels, 44100 Hz): unavailable", True),
        (0, b"AUDIO OPEN FAILED", True),
        (0, b"unrecognized backend diagnostic", False),
        (0, b"", False),
        (1, b"", True),
    ],
)
def test_ffplay_failure_detection(ding, monkeypatch, capsys, returncode, diagnostic, fallback):
    monkeypatch.setattr(ding, "available_players", lambda: [(backend(ding, "ffplay"), "/ffplay"), (backend(ding, "play"), "/play")])
    calls = []
    paths = []

    def run(command, **kwargs):
        calls.append(command[0])
        paths.append(pathlib.Path(command[-1]))
        assert paths[-1].is_file()
        assert kwargs["stdin"] == kwargs["stdout"] == subprocess.DEVNULL
        assert 0 < kwargs["timeout"] <= ding.ATTEMPT_SECONDS
        if command[0] == "/ffplay":
            assert kwargs["stderr"] == subprocess.PIPE
            return subprocess.CompletedProcess(command, returncode, stderr=diagnostic)
        assert kwargs["stderr"] == subprocess.DEVNULL
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(ding.subprocess, "run", run)
    success, failures = ding.play_tone(0, 0.5)
    assert success
    assert bool(failures) == fallback
    assert calls == (["/ffplay", "/play"] if fallback else ["/ffplay"])
    assert all(not path.parent.exists() for path in paths)
    assert capsys.readouterr() == ("", "")


def test_ffplay_failure_is_quiet_and_preview_fails(ding, monkeypatch, capsys):
    monkeypatch.setattr(ding, "available_players", lambda: [(backend(ding, "ffplay"), "/ffplay")])
    monkeypatch.setattr(ding.subprocess, "run", lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stderr=b"audio open failed PRIVATE_BACKEND_DETAILS"))
    assert ding.main([notification()]) == 0
    assert capsys.readouterr() == ("", "")
    assert ding.main(["--preview"]) == 1
    captured = capsys.readouterr()
    assert captured.err
    assert "PRIVATE_BACKEND_DETAILS" not in captured.err


def test_backend_descriptors_construct_commands_on_supported_platforms(ding, monkeypatch):
    assert len({item.name for item in ding.PLAYER_BACKENDS}) == len(ding.PLAYER_BACKENDS)
    monkeypatch.setattr(ding.shutil, "which", lambda name: "/tools/" + name)
    monkeypatch.setattr(ding.os, "access", lambda *_args: False)
    observed = set()
    for platform in ("linux", "linux2", "darwin", "win32", "freebsd"):
        monkeypatch.setattr(ding.sys, "platform", platform)
        for item, executable in ding.available_players():
            observed.add(item.name)
            command = ding.player_command(item, executable, pathlib.Path("/tmp/tone.wav"))
            assert command[0] == executable
            assert command[-1] == "/tmp/tone.wav"
    assert observed == {item.name for item in ding.PLAYER_BACKENDS}


@pytest.mark.skipif(not sys.platform.startswith("linux") or shutil.which("ffplay") is None, reason="ALSA reproduction requires Linux and ffplay")
def test_real_ffplay_audio_open_failure_uses_fallback(ding, monkeypatch, tmp_path):
    executable = shutil.which("ffplay")
    assert executable is not None
    config = tmp_path / "alsa.conf"
    config.write_text("pcm.!default { type ding_test_nonexistent }\n")
    monkeypatch.setenv("SDL_AUDIODRIVER", "alsa")
    monkeypatch.setenv("ALSA_CONFIG_PATH", str(config))
    marker = tmp_path / "fallback"
    fallback = tmp_path / "play"
    fallback.write_text("#!/bin/sh\n: > {}\n".format(shlex.quote(str(marker))))
    fallback.chmod(0o700)
    monkeypatch.setattr(ding, "available_players", lambda: [(backend(ding, "ffplay"), executable), (backend(ding, "play"), str(fallback))])
    success, failures = ding.play_tone(0, 0.5)
    assert success
    assert failures
    assert marker.exists()
