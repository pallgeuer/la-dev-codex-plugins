"""Standalone completion-sound synthesis, notification, and playback contracts."""

import array
import importlib.util
import json
import math
import os
import pathlib
import shlex
import shutil
import subprocess
import sys
import wave

import pytest
import tomli

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "codex_turn_ding.py"


@pytest.fixture
def ding():
    spec = importlib.util.spec_from_file_location("codex_turn_ding", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def backend(ding, name):
    return next(item for item in ding.PLAYER_BACKENDS if item.name == name)


def notification(thread_id="chat-one", **fields):
    return json.dumps(dict({"type": "agent-turn-complete", "thread-id": thread_id}, **fields))


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


def test_notification_argument_is_data_and_volume_zero_silences(ding, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(ding, "play_tone", lambda *args: (calls.append(args) or True, []))
    thread = 'chat\n"$(touch /tmp/never-run);`echo unsafe`\u00e9'
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
    [("afplay", []), ("paplay", ["--client-name=Codex turn ding"]), ("pw-play", []), ("aplay", ["-q"]), ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "error"]), ("play", ["-q"])],
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
@pytest.mark.parametrize("volume", [0.85, 0.5])
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
    assert tomli.loads(capsys.readouterr().out)["notify"][-1] == str(SCRIPT)


def test_toml_string_round_trips_scalar_characters(ding):
    value = "".join(chr(code) for code in range(128)) + "\u00e9\u2028\uffff\U0001f514\U00020000\U0010ffff"
    entry = "value = " + ding.toml_string(value)
    assert entry.isascii()
    assert tomli.loads(entry)["value"] == value


@pytest.mark.parametrize("interpreter", ["/tools/\U0001f514/python3", '/tools/quote"back\\slash\t\u00e9/python3'])
def test_configuration_preserves_interpreter_path(ding, monkeypatch, interpreter):
    monkeypatch.setattr(ding.sys, "executable", interpreter)
    command = tomli.loads(ding.configuration(ding.DEFAULT_VOLUME))["notify"]
    assert command == [interpreter, "-I", str(SCRIPT)]


@pytest.mark.parametrize("surrogate_codepoint", [0xD800, 0xDFFF, 0xDCFF])
@pytest.mark.parametrize("path_source", ["script", "interpreter"])
def test_unrepresentable_configuration_fails_cleanly(ding, monkeypatch, capsys, surrogate_codepoint, path_source):
    surrogate = chr(surrogate_codepoint)
    if path_source == "script":
        monkeypatch.setattr(ding, "__file__", "/tmp/" + surrogate + "/ding.py")
    else:
        monkeypatch.setattr(ding.sys, "executable", "/tmp/" + surrogate + "/python3")
    assert ding.main(["--print-config"]) == 1
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
