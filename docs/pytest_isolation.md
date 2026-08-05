# Pytest working-directory isolation

The optional pytest integration gives explicitly opted-in tests a private working directory and can place otherwise unmarked tests in one configured session-shared guard. Explicit tests choose one of two private isolation modes according to what the test should be allowed to do in its current working directory.

## Isolation modes at a glance

The plugin defines two markers, with matching fixtures:

- `@pytest.mark.isolated_cwd` provides a fresh, writable working directory. Use it for code that intentionally reads or writes relative paths, so its files stay inside a disposable per-test sandbox instead of reaching the checkout.
- `@pytest.mark.guarded_cwd` provides a read-only working directory containing deliberately malformed configuration. Use it for code that should not depend on the process working directory, so accidental relative file access, output, or configuration discovery becomes visible during the test.

Use a marker when the test only needs the isolation behavior. Request the matching `isolated_cwd` or `guarded_cwd` fixture when the test also needs the working-directory path. Markers can also be applied at class or module scope to establish the mode for a group of tests.

Installing the package never activates the plugin automatically: there is no `pytest11` entry point. Loading the plugin also leaves unmarked tests untouched by default, without working-directory mutation, environment mutation, or temporary-directory allocation. A downstream suite may separately configure the shared guard described below. The two explicit private modes are alternatives and cannot be combined on one test.

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

The `la_dev_codex_plugins.pytest_isolation` package itself does not import pytest or eagerly load the plugin. Downstream suites must not override the `guarded_cwd` or `isolated_cwd` fixture names while using the plugin; fixture overriding would make request-based activation ambiguous and is unsupported. Shared policy customization uses the process-global pytest hook documented below.

## Shared guard for unmarked tests

A suite can opt every otherwise unmarked test into one shared guarded CWD with this exact `pyproject.toml` configuration:

```toml
[tool.pytest.ini_options]
la_dev_cwd_isolation_unmarked = "shared_guarded"
```

`la_dev_cwd_isolation_unmarked` is string-valued. Its accepted values are `none`, the default described above, and `shared_guarded`. Every other value, including differently cased or whitespace-polluted spellings, is a usage error before test execution or shared filesystem allocation. There are no command-line aliases or environment-variable equivalents.

With `shared_guarded`, each pytest process creates one session boundary using the usual `cwd/` and `tmp/` layout. Each xdist worker is a separate process and therefore creates its own boundary; no xdist integration or cross-worker state is involved. Session start resolves the policy and initializes pytest's temporary factory, then the end of collection creates and hardens the shared guard before the first test even when that test requests private isolation. The process remains in its ordinary CWD between tests.

Before pytest sets up any fixture for an item, the plugin verifies the recorded identities and modes of the shared boundary, guarded `cwd/`, and writable `tmp/`, then enters the verified CWD descriptor. Unmarked tests and all broader-scoped fixtures remain in that stable shared layer. An explicitly private test temporarily enters its unique private boundary for function-scoped fixtures and the test body, restores the shared layer before module- or session-scoped fixture finalizers run, and finally leaves the shared layer after pytest completes the item's broader fixture teardown. Without configured shared mode, broader fixtures instead use the ordinary process CWD. An escaped, inaccessible, deleted, symlink-substituted, identity-replaced, or root-mode-mutated shared layout fails concisely after restoration is attempted. Layout corruption also fails before another test or nested private allocation can use the guard, and the plugin never reconstructs a deliberately corrupted shared tree.

The default shared poison policy contains the same malformed `pyproject.toml` used by private guarded mode. A project can replace it and optionally create a neutral configuration boundary above both `cwd/` and `tmp/` by implementing one process-global hook in the root `conftest.py` or an early-loaded pytest plugin:

```python
def pytest_la_dev_cwd_isolation_shared_policy(config):
    return {
        "boundary_files": {
            "pyproject.toml": "[tool.project]\n",
        },
        "poison_files": {
            "pyproject.toml": "[tool.project_specific_guard\n",
            "config/tool.ini": "[invalid",
        },
    }
```

The hook may return `None` or a mapping containing only `boundary_files` and `poison_files`. There may be at most one non-`None` provider in a pytest process. A conftest below pytest's root is rejected because partial path selection may not load it; this includes provider objects whose hook implementation is defined by a registered nested conftest. Placing the provider at the root or in an early plugin makes the policy independent of collection order and selected test paths. Early plugin modules are identified by how pytest loaded them rather than by filename, so a deliberately loaded plugin module named `conftest.py` remains valid. Under the cooperative-suite contract, opaque provider objects that cannot be attributed to a conftest are treated as early-plugin registrations. Omitting `poison_files` retains the default, while specifying it uses complete replacement semantics and `{}` creates a poison-free read-only guard. Omitting `boundary_files` creates no neutral ancestor files. The boundary mapping cannot use the reserved `cwd/` or `tmp/` paths.

Both values must map filesystem-encodable string relative paths to UTF-8-encodable string contents and follow the private poison policy's normalization and collision rules. Files receive mode `0400` and nested policy directories receive mode `0500`. The plugin copies and validates the complete policy once at session start, before initializing pytest's temporary root or creating its own boundary, so later source-mapping mutation cannot change the active policy. Boundary creation records an exact compact manifest of expected paths, entry types, modes, and SHA-256 content hashes, then releases the original path-to-content mappings. Session teardown validates the boundary and guarded policy trees against this manifest before cleanup; only the writable `tmp/` subtree may contain arbitrary entries. This one-time exact check detects policy corruption without multiplying policy-tree traversal by the number of tests. Invalid global policy produces one pytest usage error rather than one fixture error per test.

From collection finish through session finish, `TMPDIR`, `TEMP`, and `TMP` point to the shared writable `tmp/`, and `tempfile.tempdir` is cleared so standard-library temporary APIs rediscover it. The lifecycle layers verify the fixed-size shared layout and reassert those values before every test, before private allocation, after private function-fixture teardown, and after broader fixture finalization, preventing direct process-global mutations from leaking to later tests. The directory persists across tests, although standard temporary APIs continue to create unique descendants. An explicitly private test temporarily redirects these values to its own private `tmp/`, then restores and revalidates the canonical shared values.

Pytest's own `tmp_path` and `tmpdir` factory is initialized before collection and session redirection, so pytest-managed artifacts remain outside the plugin boundary and follow pytest's normal retention and permission behavior. The plugin preserves `tempfile.tempdir` around that initialization, preventing pytest's call to `tempfile.gettempdir()` from populating the process cache before collection. The plugin does not chmod pytest-owned paths. Standard-library temporary artifacts remain inside shared `tmp/` and are removed with the plugin boundary. At session teardown, the plugin restores the exact initial CWD, environment-variable presence and values, and prior `tempfile.tempdir`, then opens the recorded boundary, `cwd/`, and `tmp/` through verified no-follow descriptors before removing anything. Missing or identity-replaced children preserve the complete boundary without traversal. If cleanup of a nested private boundary was incomplete, the plugin verifies the accessible shared layout and policy but preserves the complete shared boundary instead of allowing outer `tmp/` cleanup to traverse the uncertain private root. Mode or policy corruption is reported but can still be removed when every recorded identity remains safely verified.

Explicit isolation takes precedence for function-scoped fixtures and the test body. `isolated_cwd` creates its usual private writable boundary, and `guarded_cwd` creates its usual private guarded boundary with marker-specific poison merge or replacement semantics. Session- and module-scoped fixtures remain in the stable outer shared guard, while these per-test boundaries are intentionally nested below shared `tmp/`, so boundary policy files form a neutral ancestor for private working directories as well. Here, private means unique to one test, not independent of the shared filesystem root. A matching marker and fixture still create one private boundary. Explicit opposite modes remain an error. The `guarded_cwd` fixture never returns the shared path, and no fixture exposes that path; a shared test can inspect `pathlib.Path.cwd()` when needed.

Shared guarding is correctness isolation for cooperative test suites, not a security sandbox against code already running with the pytest process's privileges. Tests must not deliberately chmod, replace, delete, add to, race, or mutate the shared guarded or boundary policy trees; use explicit `isolated_cwd` or private `guarded_cwd` for intentional CWD manipulation. Recorded layout identity and root-mode changes fail immediately, while nested policy modes, contents, and unexpected entries are reported by the exact session-teardown check and may therefore affect intervening tests. Descriptor-anchored cleanup still refuses to traverse an identity-uncertain recorded boundary, `cwd/`, or `tmp/`, and an uncertain nested private boundary prevents deletion of its outer shared boundary. Owner mode bits remain advisory for root/elevated users and filesystems that do not enforce them. CWD, environment variables, `tempfile.tempdir`, and umask are process-global and must not race in-process threads. Native Windows and WSL remain unsupported.

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

`poison_files` must be `None` or map filesystem-encodable string relative paths to UTF-8-encodable string contents. `None` is equivalent to an empty custom mapping, so the default poison remains controlled by `include_default_poison`. Contents are written exactly as UTF-8 without an implicit newline. Supplied entries override the default at the same normalized path. Absolute, empty, `.`, and any path containing a `..` component are rejected, as are duplicate normalized paths and file/directory collisions. `include_default_poison` must be a Boolean and defaults to `True`. No positional or unknown marker arguments are accepted.

A guarded test must finish in its guarded `cwd/`. Directory identity rather than lexical spelling is compared, so equivalent paths through a symlinked temporary root are accepted. Finishing in another accessible directory is a leak and fails the test after restoration. An inaccessible or deleted final CWD, or a failure to inspect its identity, also fails after restoration. Cleanup verifies the boundary and original guarded identity, then restores directory traversal permissions and removes the tree in one no-follow descriptor traversal. Regular files, symbolic links, and special files are never chmodded during teardown.

Owner mode bits do not reliably prevent writes by root/elevated users or on filesystems that do not enforce them. The malformed configuration and CWD-leak checks still apply in those environments; tests must not claim that mode bits constrain root.

## Private isolation: Marker inheritance and conflicts

The nearest marker of one name supplies configuration, so a class or function marker can replace a module-level guarded configuration. Repeating the same mode is valid. A matching marker and fixture also activate only one setup/teardown cycle.

Every applicable combination of explicit `guarded_cwd` and `isolated_cwd` is a setup error for the affected test. This includes inherited opposite markers, opposite marker/fixture combinations, and requesting both fixtures. Neither explicit mode silently overrides the other. The configured shared default does not participate in this conflict: either explicit mode overrides it. `isolated_cwd` accepts no arguments.

## Private isolation: Process state and teardown

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

A plugin-wide function-scoped autouse dispatcher enters private isolation after broader fixture setup but before downstream function-scoped fixtures, and leaves it after those function fixtures finalize but before module- or session-scoped finalizers. The private teardown inspects the test's final CWD, attempts to restore the outer CWD, restores all three environment variables and the exact `tempfile.tempdir` value, and removes the boundary through verified descriptors. An outer runtest-protocol hook performs emergency restoration when Ctrl-C or `pytest.exit()` bypasses normal teardown; setup and emergency restoration preserve the original exception or interrupt even when restoration also reports failures. Restoration is attempted before ordinary leak failures are reported, including after assertion failures, skips, fixture failures, and partial isolation setup failures. Boundary construction records each identity before subsequent fallible setup work, so a partial failure removes every safely identified component while preserving entries that exist without a recorded identity. If restoring the original CWD fails, environment restoration and cleanup still proceed. Cleanup opens and verifies the recorded boundary, `cwd/`, and `tmp/` before traversal; any missing or changed recorded identity preserves the boundary and replacement rather than deleting uncertain data. Writable descendants have owner access restored descriptor-relatively before they are opened, allowing permission-testing trees to be cleaned without following symbolic links. Policy verification and cleanup use iterative descriptor stacks rather than Python recursion; descriptor exhaustion is reported as an ordinary teardown failure and preserves the affected boundary.

CWD and environment variables are process-global. Privately isolated tests must not race threads that use either state. Each pytest-xdist worker is a separate process and receives independent private per-test boundaries; the plugin does not provide thread isolation.

The integration officially supports Ubuntu 18.04 or newer and macOS 14 or newer. General POSIX Linux compatibility is intended. Native Windows and WSL are unsupported and untested.

Private isolation without configured shared mode deliberately does not invent a neutral pytest configuration boundary. In shared mode, downstream projects can use `boundary_files` to stop tool-specific ancestor configuration discovery for both shared and nested private working directories.
