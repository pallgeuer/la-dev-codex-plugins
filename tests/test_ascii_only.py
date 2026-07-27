"""ASCII-only repository source and configuration checks."""

import subprocess
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_NON_ASCII = {
    PurePosixPath("plugins/la-review/skills/loupe/SKILL.md"): {"\N{MIDDLE DOT}"},
}


def tracked_files():
    """Return the repository files known to Git."""
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(REPOSITORY_ROOT),
        stdout=subprocess.PIPE,
        check=True,
    )
    return [PurePosixPath(path.decode("utf-8")) for path in completed.stdout.split(b"\0") if path]


def test_tracked_text_files_use_only_allowed_non_ascii_characters():
    unexpected = []
    for relative_path in tracked_files():
        path = REPOSITORY_ROOT.joinpath(*relative_path.parts)
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        allowed = ALLOWED_NON_ASCII.get(relative_path, set())
        for line_number, line in enumerate(text.splitlines(), 1):
            characters = sorted({character for character in line if not character.isascii() and character not in allowed})
            if characters:
                escaped = ", ".join("U+{:04X}".format(ord(character)) for character in characters)
                unexpected.append("{}:{} ({})".format(relative_path, line_number, escaped))
    assert not unexpected, "Unexpected non-ASCII characters:\n{}".format("\n".join(unexpected))
