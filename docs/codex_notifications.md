# Codex completion sounds

Use the standalone [codex_turn_ding.py helper](../scripts/codex_turn_ding.py) to play a notification sound after every completed Codex CLI turn, even while the terminal is focused. Each chat has a constant pitch, including when resumed. The helper is independent of the marketplace plugins and Python package: no plugin, package installation, `uv`, or third-party Python modules are required.

## Requirements

- Python 3.6 or newer. Ubuntu 18.04+ includes a suitable system Python; current macOS releases require a separate Python installation. Use `python3 --version` to check. The [Python macOS guide](https://docs.python.org/3/using/mac.html) covers installation.
- A working local audio output and one supported playback command. An installed executable alone does not prove that an audio server or device is available.
- Codex CLI with the user-level [`notify` setting](https://learn.chatgpt.com/docs/config-file/config-advanced#notifications), emitting `agent-turn-complete` with a `thread-id`.

Playback preference is platform-specific:

| Platform | Preferred players, in order                           | Optional fallbacks          |
|----------|-------------------------------------------------------|-----------------------------|
| macOS    | Built-in `/usr/bin/afplay`                            | FFmpeg `ffplay`, SoX `play` |
| Linux    | PulseAudio `paplay`, PipeWire `pw-play`, ALSA `aplay` | FFmpeg `ffplay`, SoX `play` |

No Linux playback command is assumed to exist on every fresh installation. For Ubuntu, `paplay` is supplied by `pulseaudio-utils`, `pw-play` by `pipewire-bin`, and `aplay` by `alsa-utils`; install a client appropriate to your existing audio setup. For example, on an Ubuntu desktop already using PulseAudio or its PipeWire compatibility service:

```bash
sudo apt install pulseaudio-utils
```

The helper never installs software, contacts the network, changes the default output, unmutes devices, or alters system volume. Linux distributions beyond Ubuntu are intended to work when these requirements are met, but follow the repository's [operating-system support policy](../README.md#operating-system-support). Native Windows and WSL are not supported.

## Install

Choose an existing Codex marketplace checkout or obtain your own checkout, then copy the helper using the shared steps below.

### Reuse Codex's marketplace checkout

If you already installed a plugin from this marketplace, Codex normally already has a full checkout of this repository: you do not need to clone it again. The full marketplace checkout is separate from the versioned installed-plugin payloads under `plugins/cache/`.

Find the marketplace named `la-dev-codex-plugins` and its `root` path:

```bash
codex plugin marketplace list --json
```

Change into the reported root. A common location is the following, but use the reported path if it differs:

```bash
cd "${CODEX_HOME:-$HOME/.codex}/.tmp/marketplaces/la-dev-codex-plugins"
```

Check that `scripts/codex_turn_ding.py` exists there. If the checkout predates this helper, refresh it through Codex rather than running `git pull` in its managed checkout:

```bash
codex plugin marketplace upgrade la-dev-codex-plugins
```

After refreshing, locate the root again and re-enter it because Codex may replace its managed checkout. A marketplace pinned to an older release may still lack the helper; choose a ref containing it or use your own checkout below.

Continue with **Copy and configure the helper** below. Copy the file out of the managed checkout; do not point `notify` directly at a temporary marketplace path or versioned plugin-cache path, which Codex can replace or remove.

### Obtain your own checkout

If you do not have a suitable existing checkout, obtain this repository and enter its root. Use a reviewed release tag instead of `main` if you need a pinned version:

```bash
git clone https://github.com/pallgeuer/la-dev-codex-plugins.git
cd la-dev-codex-plugins
```

### Copy and configure the helper

Copy the self-contained script into your active Codex home. The following deliberately refuses to replace an existing file; for an update, review the replacement first as described below:

```bash
codex_ding_home="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$codex_ding_home/hooks"
python3 -c 'import pathlib, sys; source = pathlib.Path("scripts/codex_turn_ding.py"); destination = pathlib.Path(sys.argv[1]) / "hooks/codex_turn_ding.py"; destination.open("xb").write(source.read_bytes())' "$codex_ding_home"
```

Keep this shell variable available for the following commands. The script is run through Python and does not need executable permissions. Use a durable Python installation: removing the interpreter later will break its generated notification command.

Check playback availability, then preview all 13 notes. **The default amplitude is 85%; start with `--volume 0.25` if your speakers or headphones are loud.** Amplitude is a digital signal fraction, not a percentage of perceived loudness or system volume.

```bash
python3 "$codex_ding_home/hooks/codex_turn_ding.py" --diagnose
python3 "$codex_ding_home/hooks/codex_turn_ding.py" --preview --volume 0.25
python3 "$codex_ding_home/hooks/codex_turn_ding.py" --preview
```

Print a complete configuration entry using the installed script and current Python interpreter:

```bash
python3 "$codex_ding_home/hooks/codex_turn_ding.py" --print-config
```

Merge the printed `notify = [...]` line into **the root of `"$codex_ding_home/config.toml"`, before any `[table]` headers**. Do not put it under `[tui]`. The output includes escaped absolute paths and Python's `-I` isolated mode; do not replace them with `~` or `$HOME`, which are not shell-expanded inside this command array. The paths are generated for each installation, not hardcoded into the distributed helper. Unicode paths, including emoji, are emitted with TOML-compatible ASCII escapes. Paths containing undecodable filesystem bytes or lone Unicode surrogates cannot be represented in TOML: `--print-config` exits nonzero without emitting an entry; install under a valid Unicode path instead.

If `notify` already exists, deliberately replace it or compose both actions using your own dispatcher. Do not add a second `notify` key or silently discard your previous notification behavior. This helper receives one JSON argument, not JSON on standard input; a dispatcher must forward that argument intact without evaluating it as shell code.

Restart Codex CLI after editing its configuration. Complete two turns in one chat to hear the same pitch, then try another chat. A different chat can legitimately share the same note.

## Tune the volume

Use `--volume` with a finite value from 0 to 1. To produce a configuration line with a quieter setting:

```bash
python3 "$codex_ding_home/hooks/codex_turn_ding.py" --preview --volume 0.5
python3 "$codex_ding_home/hooks/codex_turn_ding.py" --print-config --volume 0.5
```

Replace your existing `notify` entry with the new line and restart Codex. `--volume 0` silences notification playback. The helper never boosts or changes the system/player stream volume.

## Sound and pitch assignment

The 13 notes are C4, C#4, D4, D#4, E4, F4, F#4, G4, G#4, A4, A#4, B4, and C5 (approximately 262-523 Hz). The note offset is the big-endian SHA-256 digest of the UTF-8 `thread-id`, modulo 13. Frequency is `261.6255653 * 2 ** (offset / 12)` Hz. Turn identifiers, working directories, and message text do not affect the pitch. No assignment database is written; this mapping is stable across invocations and resumes. Two independent chats have approximately a 1-in-13 chance of matching, so sounds are cues rather than unique chat identifiers.

Each tone combines a fundamental and a quiet second harmonic. It has an 8 ms attack, a 200 ms sustained body, an exponential decay with a 220 ms time constant, and a final 25 ms fade. A 250 ms silent lead-in gives output paths such as HDMI time to start; the tone itself lasts 1.1 seconds. The WAV is mono, 44.1 kHz, signed 16-bit PCM.

Only `agent-turn-complete` events with a nonempty string `thread-id` play a sound. Approval requests and interruptions receive no additional sound. Malformed or unsupported notifications are ignored. Normal hook execution is quiet and best effort; use the interactive tools for failures. WAV files are created in a private temporary directory and cleaned up after playback. A player gets at most three seconds, with an eight-second total playback budget across fallback attempts. No messages or notification payloads are logged or sent to the audio tools. Backend discovery and command construction share one ordered set of definitions. For `ffplay`, fallback also recognizes known fatal audio-open, SDL initialization, and file/filtergraph diagnostics, because some versions exit zero after these failures. Unrecognized diagnostics with a zero exit status do not trigger fallback, reducing the risk of a second tone after successful playback; this cannot detect every playback failure. Captured backend diagnostics remain internal, and preview reports generic failure descriptions.

## Troubleshoot

- Run `--diagnose` to inspect Python and available players. It reports executable availability, not audio-server connectivity. Run `--preview` to test the complete path; it reports a failure and exits nonzero if all players fail.
- If short sounds disappear but sustained audio works, the output may need time to wake. The default lead-in and sustained body help, but some hardware needs longer startup. Compare normal audio on the same device before increasing amplitude.
- If sound goes to headphones or another output, check system audio settings and saved application routing. PulseAudio identifies the stream as **Codex turn ding**. Select the desired output there; the helper follows player routing and does not force a device. For local Linux testing, standard player environment settings such as `PULSE_SINK` can select an output for `paplay` without hardcoding that device in this project.
- If everything is faint, check monitor, speaker, headphone, mixer, and per-application volume. Increasing the helper past full scale is not supported and would cause clipping.
- SSH sessions, containers, and headless hosts may have no usable audio session. Playback occurs on the machine running Codex; the helper does not forward sound to your laptop. A terminal bell does not provide the required per-chat pitch and is not used as a fallback.
- If manual previews work but notifications do not, check the top-level configuration placement, active `CODEX_HOME`, installed paths, Python availability, and restart Codex. Retain existing TUI notifications or deliberately adjust them separately if your terminal also makes a sound.

## Update or remove

For updates, review the new script and replace the installed copy from your checkout. The note mapping remains unchanged. Re-run `--preview`; regenerate the configuration if the interpreter, installed path, or volume changes:

```bash
cp scripts/codex_turn_ding.py "$codex_ding_home/hooks/codex_turn_ding.py"
```

To disable notifications, remove the `notify` entry (or restore your previous dispatcher) and restart Codex. You may then delete the installed helper. Neither installing marketplace plugins nor installing the Python package installs, updates, enables, or removes this standalone helper.
