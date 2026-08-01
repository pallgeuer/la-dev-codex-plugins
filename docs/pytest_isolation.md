# Pytest working-directory isolation

The optional pytest integration gives individual tests a private working directory and redirects their temporary files away from the repository checkout. Each opted-in test chooses one of two isolation modes according to what the test should be allowed to do in its current working directory.

## Isolation modes at a glance

The plugin defines two markers, with matching fixtures:

- `@pytest.mark.isolated_cwd` provides a fresh, writable working directory. Use it for code that intentionally reads or writes relative paths, so its files stay inside a disposable per-test sandbox instead of reaching the checkout.
- `@pytest.mark.guarded_cwd` provides a read-only working directory containing deliberately malformed configuration. Use it for code that should not depend on the process working directory, so accidental relative file access, output, or configuration discovery becomes visible during the test.

Use a marker when the test only needs the isolation behavior. Request the matching `isolated_cwd` or `guarded_cwd` fixture when the test also needs the working-directory path. Markers can also be applied at class or module scope to establish the mode for a group of tests.

Isolation is always explicit. Installing the package never activates the plugin automatically: there is no `pytest11` entry point, and unmarked tests that request neither fixture receive no working-directory mutation, environment mutation, or temporary-directory allocation. The two modes are alternatives and cannot be combined on one test.

## Installation and loading

Install the narrow extra or the equivalent development extra:

```text
python -m pip install 'la-dev-codex-plugins[pytest]'
python -m pip install 'la-dev-codex-plugins[dev]'
```

Both extras declare `pytest>=7.0.1`; the base installation remains dependency-free. Explicitly load the plugin on the command line:

```text
pytest -p la_dev_codex_plugins.pytest_isolation.plugin
```

Alternatively, opt in for a repository or test subtree from its pytest configuration:

```python
pytest_plugins = ("la_dev_codex_plugins.pytest_isolation.plugin",)
```

The `la_dev_codex_plugins.pytest_isolation` package itself does not import pytest or eagerly load the plugin. Downstream suites must not override the `guarded_cwd` or `isolated_cwd` fixture names while using the plugin; fixture overriding would make request-based activation ambiguous and is unsupported.

## Writable isolation: `isolated_cwd`

Request the fixture when the test needs the directory path:

```python
def test_generates_files(isolated_cwd):
    output = isolated_cwd / "output.txt"
    output.write_text("result", encoding="utf-8")
```

Use the marker when the path is not needed as an argument:

```python
import pytest


@pytest.mark.isolated_cwd
def test_uses_relative_paths():
    ...
```

The test begins in a fresh writable `cwd/`. It may finish in another accessible directory; the plugin silently restores the original CWD because legitimate sandboxed code can call `chdir`. It fails the affected test only if the final CWD cannot be inspected or the original CWD cannot be restored.

## Guarded isolation: `guarded_cwd`

Guarded mode exposes accidental reads from or writes to the current working directory:

```python
import pytest


@pytest.mark.guarded_cwd
def test_does_not_discover_cwd_configuration():
    ...
```

The fixture form returns the guarded path:

```python
def test_stays_inside_guard(guarded_cwd):
    assert guarded_cwd.name == "cwd"
```

By default, `cwd/pyproject.toml` contains the exact UTF-8 text `[tool.la_dev_cwd_guard\n`, which is deliberately malformed. Before test code runs, every directory in the guarded tree has mode `0500` and every poison file has mode `0400`.

Customize poison files on the nearest applicable marker:

```python
@pytest.mark.guarded_cwd(
    poison_files={"config/tool.ini": "[invalid"},
    include_default_poison=False,
)
def test_custom_guard():
    ...
```

`poison_files` must be `None` or map string relative paths to string contents. `None` is equivalent to an empty custom mapping, so the default poison remains controlled by `include_default_poison`. Contents are written exactly as UTF-8 without an implicit newline. Supplied entries override the default at the same normalized path. Absolute, empty, `.`, and any path containing a `..` component are rejected, as are duplicate normalized paths and file/directory collisions. `include_default_poison` must be a Boolean and defaults to `True`. No positional or unknown marker arguments are accepted.

A guarded test must finish in its guarded `cwd/`. Directory identity rather than lexical spelling is compared, so equivalent paths through a symlinked temporary root are accepted. Finishing in another accessible directory is a leak and fails the test after restoration. An inaccessible or deleted final CWD, or a failure to inspect its identity, also fails after restoration. Before cleanup, the original guarded identity is verified and directory traversal permissions are restored through no-follow directory descriptors. Regular files, symbolic links, and special files are never chmodded during teardown.

Owner mode bits do not reliably prevent writes by root/elevated users or on filesystems that do not enforce them. The malformed configuration and CWD-leak checks still apply in those environments; tests must not claim that mode bits constrain root.

## Both isolation: Marker inheritance and conflicts

The nearest marker of one name supplies configuration, so a class or function marker can replace a module-level guarded configuration. Repeating the same mode is valid. A matching marker and fixture also activate only one setup/teardown cycle.

Every applicable combination of `guarded_cwd` and `isolated_cwd` is a setup error for the affected test. This includes inherited opposite markers, opposite marker/fixture combinations, and requesting both fixtures. Neither mode silently overrides the other. `isolated_cwd` accepts no arguments.

## Both isolation: Process state and teardown

Every opted-in test receives one private boundary:

```text
la-dev-pytest-isolation-.../
|-- cwd/
`-- tmp/
```

The sibling `tmp/` remains writable in both modes. Before other function-scoped fixtures run, the plugin:

- saves the exact `os.getcwd()` value;
- saves the exact value or absence of `TMPDIR`, `TEMP`, and `TMP`;
- saves the exact `tempfile.tempdir` cache;
- points all three environment variables at the absolute `tmp/` path;
- sets `tempfile.tempdir = None` so the standard library rediscovers the redirected directory; and
- changes to `cwd/`.

The private boundary and writable directories receive explicit owner-accessible modes after creation, so a restrictive process umask cannot make isolation setup or cleanup unusable. Guarded mode subsequently applies its documented read-only owner modes to the guarded tree while leaving `tmp/` writable.

The autouse dispatcher is established before ordinary function-scoped fixtures, so its finalizer runs after their finalizers. It inspects the test's final CWD, attempts to restore the original CWD, restores all three environment variables and the exact `tempfile.tempdir` value, restores guarded directory permissions, and removes the boundary. Restoration is attempted before leak failures are reported, including after assertion failures, skips, other fixture setup/call/teardown failures, and partial isolation setup failures. If restoring the original CWD fails, environment and permission restoration still proceeds and the failure is reported directly.

CWD and environment variables are process-global. Opted-in tests must not race threads that use either state. Each pytest-xdist worker is a separate process and receives independent per-test boundaries; the plugin does not provide thread isolation.

The integration officially supports Ubuntu 18.04 or newer and macOS 14 or newer. General POSIX Linux compatibility is intended. Native Windows and WSL are unsupported and untested.

The plugin deliberately does not invent a neutral pytest configuration boundary. A downstream project that needs a tool to stop configuration discovery at a specific file must add that tool-specific boundary itself.
