"""Standalone completion-sound synthesis, notification, and playback contracts."""

import array
import importlib.util
import json
import math
import os
import pathlib
import shutil
import subprocess
import sys
import wave

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "codex_turn_ding.py"


@pytest.fixture
def ding():
    spec = importlib.util.spec_from_file_location("codex_turn_ding", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    assert [name for name, _path in players] == expected
    if platform == "darwin":
        assert players[0][1] == "/usr/bin/afplay"
    monkeypatch.setattr(ding.shutil, "which", lambda _name: None)
    monkeypatch.setattr(ding.os, "access", lambda *_args: False)
    assert ding.available_players() == []


@pytest.mark.parametrize(
    ("name", "options"),
    [("afplay", []), ("paplay", ["--client-name=Codex turn ding"]), ("pw-play", []), ("aplay", ["-q"]), ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]), ("play", ["-q"])],
)
def test_player_commands_preserve_literal_paths(ding, name, options):
    path = pathlib.Path('/tmp/with spaces/"$(unsafe)\u00e9.wav')
    assert ding.player_command(name, "/tools/" + name, path) == ["/tools/" + name, *options, str(path)]


@pytest.mark.parametrize("failure", ["status", "timeout", "oserror", "success"])
def test_playback_fallback_and_cleanup(ding, monkeypatch, failure):
    monkeypatch.setattr(ding, "available_players", lambda: [("paplay", "/paplay"), ("aplay", "/aplay")])
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
    monkeypatch.setattr(ding, "available_players", lambda: [(name, "/" + name) for name in ("paplay", "pw-play", "aplay", "ffplay", "play")])
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


def test_real_player_timeout_and_temporary_cleanup(ding, monkeypatch):
    monkeypatch.setattr(ding, "available_players", lambda: [("paplay", sys.executable)])
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
    monkeypatch.setattr(ding, "available_players", lambda: [("paplay", "/paplay")])
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
    monkeypatch.setattr(ding, "available_players", lambda: [("paplay", "/paplay")])

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
    monkeypatch.setattr(ding, "available_players", lambda: [("afplay", "/usr/bin/afplay")])
    assert ding.main(["--diagnose"]) == 0
    assert "/usr/bin/afplay" in capsys.readouterr().out
    assert len(calls) == 13


def test_generated_configuration_works_after_copying(ding, tmp_path, capsys):
    installed = tmp_path / 'space and "quote" \u00e9' / "ding.py"
    installed.parent.mkdir()
    shutil.copyfile(SCRIPT, installed)
    result = subprocess.run([sys.executable, "-I", str(installed), "--print-config", "--volume", "0.5"], stdout=subprocess.PIPE, check=True)
    command = json.loads(result.stdout.decode().split("=", 1)[1])
    assert command == [str(pathlib.Path(sys.executable).absolute()), "-I", str(installed.resolve()), "--volume", "0.5"]
    completed = subprocess.run([*command, notification(type="ignored")], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    assert completed.stdout == completed.stderr == b""
    assert ding.main(["--print-config"]) == 0
    assert json.loads(capsys.readouterr().out.split("=", 1)[1])[-1] == str(SCRIPT)
