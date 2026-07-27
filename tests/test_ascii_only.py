"""ASCII-only repository source and configuration checks."""

import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_NON_ASCII = {
    PurePosixPath("plugins/la-review/skills/loupe/SKILL.md"): {"\N{MIDDLE DOT}"},
}


def ascii_path(path):
    """Return one filesystem path with non-ASCII code points escaped."""
    return str(path).encode("ascii", errors="backslashreplace").decode("ascii")


def repository_files():
    """Return existing tracked and nonignored untracked repository files."""
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=str(REPOSITORY_ROOT),
        stdout=subprocess.PIPE,
        check=True,
    )
    paths = []
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative_path = PurePosixPath(os.fsdecode(raw_path))
        path = REPOSITORY_ROOT.joinpath(*relative_path.parts)
        if not path.is_symlink() and path.is_file():
            paths.append(relative_path)
    return paths


def test_repository_files_preserves_non_utf8_paths(monkeypatch, tmp_path):
    raw_path = b"bad-\xff.py"
    relative_path = PurePosixPath(os.fsdecode(raw_path))
    tmp_path.joinpath(*relative_path.parts).write_text("ASCII\n", encoding="ascii")
    monkeypatch.setattr(sys.modules[__name__], "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, stdout=raw_path + b"\0"))
    assert repository_files() == [relative_path]
    assert ascii_path(relative_path) == "bad-\\udcff.py"


def test_repository_files_excludes_symlinks(monkeypatch, tmp_path):
    external = tmp_path.parent / "external-non-ascii.py"
    external.write_text("\u03bb\n", encoding="utf-8")
    (tmp_path / "external.py").symlink_to(external)
    (tmp_path / "broken.py").symlink_to("missing.py")
    (tmp_path / "regular.py").write_text("ASCII\n", encoding="ascii")
    monkeypatch.setattr(sys.modules[__name__], "REPOSITORY_ROOT", tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, stdout=b"external.py\0broken.py\0regular.py\0"))
    assert repository_files() == [PurePosixPath("regular.py")]


def test_repository_text_files_use_only_allowed_non_ascii_characters():
    unexpected = []
    for relative_path in repository_files():
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
                unexpected.append("{}:{} ({})".format(ascii_path(relative_path), line_number, escaped))
    assert not unexpected, "Unexpected non-ASCII characters:\n{}".format("\n".join(unexpected))
