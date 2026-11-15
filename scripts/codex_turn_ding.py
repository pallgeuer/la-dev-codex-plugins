#!/usr/bin/env python3
"""Standalone, standard-library-only Codex CLI completion sounds for POSIX hosts."""

import argparse
import collections
import hashlib
import json
import math
import os
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave

SAMPLE_RATE = 44100
NOTE_NAMES = ("C4", "C#4", "D4", "D#4", "E4", "F4", "F#4", "G4", "G#4", "A4", "A#4", "B4", "C5")
DEFAULT_VOLUME = 0.85
LEAD_SECONDS = 0.25
TONE_SECONDS = 1.1
ATTEMPT_SECONDS = 3.0
PLAYBACK_SECONDS = 8.0

PlayerBackend = collections.namedtuple("PlayerBackend", "name platforms options failure_markers")
PlayerBackend.__doc__ = "A player name, supported platforms, argv options, and lowercase fatal stderr markers."
# Table order determines preference after filtering by platform; markers enable internal stderr capture.
PLAYER_BACKENDS = (
    PlayerBackend("afplay", ("darwin",), (), ()),
    PlayerBackend("paplay", ("linux",), ("--client-name=Codex turn ding",), ()),
    PlayerBackend("pw-play", ("linux",), (), ()),
    PlayerBackend("aplay", ("linux",), ("-q",), ()),
    PlayerBackend("ffplay", ("darwin", "linux"), ("-nodisp", "-autoexit", "-loglevel", "error"), (b"audio open failed", b"failed to open file", b"could not initialize sdl", b"sdl_openaudio (")),
    PlayerBackend("play", ("darwin", "linux"), ("-q",), ()),
)


def note_index(thread_id):
    """Return the stable C4-C5 semitone offset for a UTF-8 thread identifier."""
    return int.from_bytes(hashlib.sha256(thread_id.encode("utf-8")).digest(), "big") % len(NOTE_NAMES)


def frequency_for_note(index):
    """Return the frequency in Hz for a zero-based C4-C5 semitone offset."""
    if not 0 <= index < len(NOTE_NAMES):
        raise ValueError("Note index must be between 0 and 12")
    return 261.6255653 * 2 ** (index / 12)


def envelope_at(seconds):
    """Return the attack, sustained body, decay, and final fade gain at tone time."""
    if not 0 <= seconds < TONE_SECONDS:
        return 0.0
    return min(1.0, seconds / 0.008) * math.exp(-max(0.0, seconds - 0.20) / 0.22) * min(1.0, (TONE_SECONDS - seconds) / 0.025)


def write_tone(path, index, volume):
    """Write a mono 44.1 kHz signed 16-bit WAV at the requested note and amplitude."""
    if not math.isfinite(volume) or not 0 <= volume <= 1:
        raise ValueError("Volume must be a finite number between 0 and 1")
    frequency = frequency_for_note(index)
    frames = bytearray(round(SAMPLE_RATE * LEAD_SECONDS) * 2)
    for sample_index in range(round(SAMPLE_RATE * TONE_SECONDS)):
        seconds = sample_index / SAMPLE_RATE
        phase = 2 * math.pi * frequency * seconds
        sample = volume * envelope_at(seconds) * (math.sin(phase) + 0.2 * math.sin(2 * phase)) / 1.2
        frames.extend(struct.pack("<h", round(32767 * sample)))
    with wave.open(str(path), "wb") as sound:
        sound.setparams((1, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
        sound.writeframes(frames)


def available_players():
    """Return backend descriptors and executable paths in platform preference order."""
    platform = "linux" if sys.platform.startswith("linux") else sys.platform
    players = []
    for backend in PLAYER_BACKENDS:
        if platform not in backend.platforms:
            continue
        executable = "/usr/bin/afplay" if backend.name == "afplay" and os.access("/usr/bin/afplay", os.X_OK) else shutil.which(backend.name)
        if executable:
            players.append((backend, executable))
    return players


def player_command(backend, executable, path):
    """Build a descriptor's direct WAV invocation without shell evaluation."""
    return [executable, *backend.options, str(path)]


def play_tone(index, volume):
    """Play one synthesized note; return success and safe backend failure descriptions."""
    players = available_players()
    if not players:
        return False, ["No supported audio player found; run --diagnose and see the setup guide"]
    failures = []
    with tempfile.TemporaryDirectory(prefix="codex-turn-ding-") as folder:
        path = pathlib.Path(folder) / "ding.wav"
        write_tone(path, index, volume)
        deadline = time.monotonic() + PLAYBACK_SECONDS
        for backend, executable in players:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failures.append("Playback time budget exhausted")
                break
            try:
                result = subprocess.run(
                    player_command(backend, executable, path),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE if backend.failure_markers else subprocess.DEVNULL,
                    timeout=min(ATTEMPT_SECONDS, remaining),
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                failures.append("{} unavailable or timed out".format(backend.name))
            else:
                if backend.failure_markers and any(marker in (result.stderr or b"").lower() for marker in backend.failure_markers):
                    failures.append("{} reported a playback failure".format(backend.name))
                elif result.returncode == 0:
                    return True, failures
                else:
                    failures.append("{} exited with status {}".format(backend.name, result.returncode))
    return False, failures


def notification_note(payload):
    """Return a valid completed-turn notification's note, or None for ignored input."""
    try:
        notification = json.loads(payload)
        if not isinstance(notification, dict) or notification.get("type") != "agent-turn-complete":
            return None
        thread_id = notification.get("thread-id")
        if not isinstance(thread_id, str) or not thread_id.strip():
            return None
        return note_index(thread_id)
    except (ValueError, UnicodeError, RecursionError):
        return None


def volume_argument(value):
    """Parse an amplitude fraction in the inclusive finite range 0-1."""
    try:
        volume = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Volume must be a number between 0 and 1") from None
    if not math.isfinite(volume) or not 0 <= volume <= 1:
        raise argparse.ArgumentTypeError("Volume must be a finite number between 0 and 1")
    return volume


def toml_string(value):
    """Encode a Unicode scalar string as an ASCII-only TOML basic string."""
    escaped = []
    for character in value:
        code = ord(character)
        if 0xD800 <= code <= 0xDFFF:
            raise ValueError("Installation paths must contain valid Unicode scalar values")
        if character in ('"', "\\"):
            escaped.append("\\" + character)
        elif 0x20 <= code < 0x7F:
            escaped.append(character)
        elif code <= 0xFFFF:
            escaped.append("\\u{:04x}".format(code))
        else:
            escaped.append("\\U{:08x}".format(code))
    return '"' + "".join(escaped) + '"'


def configuration(volume):
    """Return a TOML root notify entry bound to this interpreter and installed script."""
    command = [str(pathlib.Path(sys.executable).absolute()), "-I", str(pathlib.Path(__file__).resolve())]
    if volume != DEFAULT_VOLUME:
        command.extend(["--volume", str(volume)])
    return "notify = [" + ", ".join(toml_string(argument) for argument in command) + "]"


def main(argv=None):
    """Run a quiet notification handler or an explicitly selected interactive utility."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("notification", nargs="?", help="Codex's appended notification JSON")
    parser.add_argument("--volume", type=volume_argument, default=DEFAULT_VOLUME, help="Synthesis amplitude from 0 to 1 (default: 0.85)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preview", action="store_true", help="Play all 13 notes, in ascending order")
    mode.add_argument("--diagnose", action="store_true", help="Report interpreter and available playback tools without playing")
    mode.add_argument("--print-config", action="store_true", help="Print a root TOML notify entry for this installed file")
    args = parser.parse_args(argv)
    interactive = args.preview or args.diagnose or args.print_config
    if interactive and args.notification is not None:
        parser.error("Utility modes do not accept a notification argument")
    if args.print_config:
        try:
            entry = configuration(args.volume)
        except ValueError as exc:
            print("Could not generate configuration: {}".format(exc), file=sys.stderr)
            return 1
        print(entry)
        return 0
    if args.diagnose:
        players = available_players()
        print("Platform: {}\nPython: {}\nScript: {}".format(sys.platform, sys.executable, pathlib.Path(__file__).resolve()))
        print("Playback order: {}".format(", ".join("{} ({})".format(backend.name, executable) for backend, executable in players) or "none"))
        print("Output follows system/player routing; no device or system volume is changed.")
        return 0 if players else 1
    index = notification_note(args.notification) if args.notification is not None else None
    if args.preview:
        indices = range(len(NOTE_NAMES))
    elif index is None or args.volume == 0:
        return 0
    else:
        indices = (index,)
    try:
        for offset in indices:
            if args.preview:
                print("{}/13: {} ({:.1f} Hz), amplitude {}".format(offset + 1, NOTE_NAMES[offset], frequency_for_note(offset), args.volume), flush=True)
            success, failures = play_tone(offset, args.volume)
            if not success:
                if args.preview:
                    print("; ".join(failures), file=sys.stderr)
                    return 1
                return 0
            if args.preview and offset < len(NOTE_NAMES) - 1:
                time.sleep(0.65)
    except (OSError, ValueError, wave.Error) as exc:
        if args.preview:
            print("Could not play preview: {}".format(exc), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
