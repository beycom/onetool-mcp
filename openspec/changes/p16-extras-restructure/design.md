## Context

`pyproject.toml` (current state, verified at `main`@`151a52b3`, 2026-07-04) defines four
optional-dependency groups plus a convenience group:

```toml
[project.optional-dependencies]
util = [
    "formulas>=1.3.4",             # Excel formula computation for convert pack
    "openpyxl>=3.1.5",
    "pathspec>=1.1.1",
    "pymupdf>=1.27.2.3",
    "python-docx>=1.2.0",
    "python-frontmatter>=1.1.0",   # YAML frontmatter parsing for knowledge pack
    "python-pptx>=1.0.2",
    "sqlite-vec>=0.1.9",           # Vector search extension for knowledge pack
    "google-genai>=1.73.1",
    "send2trash>=2.1.0",
]
dev = [
    "beautifulsoup4>=4.14.3",
    "filelock>=3.29.0",
    "lxml>=5.3,<6",
    "markdown>=3.9",
    "openpyxl>=3.1.5",
    "sqlalchemy>=2.0.49",
    "tabulate>=0.10.0",
    "trafilatura>=2.0.0",
]
scrape = [
    "crawl4ai>=0.8.6",
]
whiteboard = [
    "pydoll-python>=2.22.1",
]
all = ["onetool-mcp[util,dev]"]
```

(line numbers: `util` block 54-65, `dev` block 66-75, `scrape` block 76-78, `whiteboard` block 79-81,
`all` line 82 — verify with a fresh `rg -n` before editing since line numbers drift; if they've moved,
proceed on the block *contents* shown above, which are the authoritative anchor, and flag the drift in
the task instead of silently trusting the stale line number.)

`all = ["onetool-mcp[util,dev]"]` does NOT include `scrape` or `whiteboard`. `scrape` staying out is
intentional (crawl4ai is a large, specialized, opt-in dependency — the maintainer ruling keeps it
that way). `whiteboard` staying out is a bug: `README.md:119` markets "Live Whiteboard" as a
headline feature, `README.md:58` documents `[all]` as "everything", but a user who runs the
documented install command gets an `ImportError` the first time they call `whiteboard.open()`.

Separately, `src/otdev/tools/excalidraw.py:119` calls pydoll's `Chrome()` with no launch options.
Recent Chrome versions ship an on-device "Gemini Nano" model (part of the built-in AI /
"Optimization Guide" feature) that a freshly-launched, unconfigured Chrome profile can silently start
downloading in the background (~4GB) the first time it's driven via CDP, along with other
non-essential background networking (component update pings, etc.). Today this is a possible surprise
for pydoll/whiteboard users; once `pydoll-python` moves into `[util]` (this change), it becomes a
near-certain surprise for anyone who installs the recommended `[util]` or `[all]` extra and calls
`whiteboard.open()` even once — so the launch-flags fix is a hard precondition of the extras move, not
an independent follow-up.

## Goals / Non-Goals

**Goals:**
- Make `onetool-mcp[all]` and `onetool-mcp[util]` both provide a fully working `whiteboard` pack with
  no `ImportError`.
- Delete the standalone `whiteboard` extra outright (V3 breaking window — no alias, no deprecation
  warning, no shim extra that silently re-exports `[util]`).
- Stop pydoll's Chrome launches from triggering the Gemini Nano background download or other
  background networking, for every whiteboard session, not just some.
- Leave every doc and error message that names install extras internally consistent with the new
  contract.

**Non-Goals:**
- Moving `src/otdev/tools/excalidraw.py` (and its `_excalidraw/` support package and tests) from
  `otdev` to `otutil` to fully align the `otdev↔[dev]` / `otutil↔[util]` package-vs-extra convention.
  This is explicitly deferred post-V3 (see proposal.md Impact — "Deliberately out of scope").
- Changing the `scrape` extra or crawl4ai — untouched by this change.
- Changing any whiteboard DSL, drawing, or session-state behavior — this change touches only the
  install contract and the Chrome launch options, nothing about what `whiteboard.draw()` etc. do.
- Editing `CHANGELOG.md` — the breaking-change note lives in this change's `proposal.md` Impact
  section; `p33-release-cut` is responsible for compiling it into the shipped changelog.

## Decisions

### D1: Fold `pydoll-python` into `[util]` rather than creating a new merged extra

Move the single line `"pydoll-python>=2.22.1"` from the `whiteboard` group into the `util` group,
then delete the (now-empty) `whiteboard` group. `all` needs no text change — it already resolves to
`[util,dev]`, so it picks up `pydoll-python` transitively the moment it's inside `[util]`.

Alternatives considered:
- **Add `whiteboard` into `all`'s bracket list instead** (`all = ["onetool-mcp[util,dev,whiteboard]"]`)
  — rejected: keeps a pointless standalone extra around with exactly one dependency and no purpose
  other than being listed inside `all`; every doc would still need a `[whiteboard]` extra entry, and
  a user could still type `pip install 'onetool-mcp[dev]'` and be missing whiteboard, which is exactly
  today's confusing state minus one bug. The maintainer ruling explicitly says "delete the whiteboard
  extra."
- **Put `pydoll-python` in `[dev]` instead of `[util]`** — rejected: the maintainer ruling is explicit
  (report R3 item 4: "move `pydoll-python` ... into `util`"). `[util]` also happens to be the smaller,
  more universally-installed extra (it's the one most non-dev users reach for), so this maximizes the
  chance a typical `[util]`-only install gets a working whiteboard.

### D2: Accept the `otdev`/`[util]` cross-grouping for V3; defer the module move

The whiteboard *module* stays in `src/otdev/tools/excalidraw.py` (part of the `otdev` package, whose
extra is conventionally `[dev]`), while its one PyPI dependency (`pydoll-python`) now lives in
`[util]`. This breaks the `otdev↔dev` / `otutil↔util` naming symmetry that holds for every other pack.

Alternatives considered:
- **(a) Accept the cross-grouping for V3 (chosen).** Extras gate only PyPI dependency resolution —
  they do not gate which package directory a tool module physically lives in, and the tool loader
  discovers `src/otdev/tools/*.py` and `src/otutil/tools/*.py` independently of which extras are
  installed. The whiteboard module ships and is discoverable regardless of which extra was installed;
  if `pydoll-python` is missing it fails gracefully with the `ImportError` hint (D3) rather than
  crashing pack discovery. Whiteboard is also arguably a general visual/diagramming tool, not a
  "dev" tool specifically, so the grouping is defensible on its own merits, not just as a compromise.
- **(b) Also move `excalidraw.py` + `_excalidraw/` + both test files to `otutil`.** Cleaner naming
  symmetry, but a much larger change: touches module import paths, pack discovery paths, test file
  locations (`tests/unit/tools/test_excalidraw.py`,
  `tests/otdev/integration/tools/test_excalidraw.py`), and any other code that imports
  `otdev.tools.excalidraw` or `otdev.tools._excalidraw` by name. Rejected for V3 as
  disproportionate to the actual bug being fixed (a broken `[all]` install); recorded as a
  rejected-for-V3 alternative to revisit post-V3.

### D3: Update the `ImportError` hint, not the exception type or trigger condition

`src/otdev/tools/excalidraw.py:106-109` currently does:

```python
except ImportError:
    raise ImportError(
        "pydoll-python is required for whiteboard. "
        "Install with: pip install 'onetool-mcp[whiteboard]'"
    ) from None
```

Only the extra name in the message string changes, from `[whiteboard]` to `[util]`. The exception
type, the `from None` (suppressing the original traceback noise), and the trigger condition (pydoll
not importable) are all unchanged — this is a one-line string edit, not a behavior change.

### D4: Chrome launch flags — construct via a small testable helper

`_open_browser()`'s inner `_start()` coroutine currently does `b = Chrome()` inside a retry loop
(`src/otdev/tools/excalidraw.py:111-127`). The fix constructs a `pydoll.browser.options.ChromiumOptions`
instance and passes it as `Chrome(options=...)`. To keep this testable without mocking pydoll's full
async browser-start flow, factor the options construction into a small private helper function,
`_chrome_options()`, that returns a fresh `ChromiumOptions` with the three flags added via
`.add_argument(...)` (verified against the installed pydoll `ChromiumOptions` API at
`.venv/lib/python3.13/site-packages/pydoll/browser/options.py`: constructor takes no arguments,
`add_argument(str)` appends to `.arguments`). `_start()` then calls `Chrome(options=_chrome_options())`
on every attempt of the retry loop (not just the first), so a retry after `NoValidTabFound` never
silently drops back to unconfigured launch options.

```python
def _chrome_options() -> Any:
    """Suppress Chrome's on-device Gemini Nano download and background networking."""
    from pydoll.browser.options import ChromiumOptions

    options = ChromiumOptions()
    options.add_argument(
        "--disable-features=OptimizationGuideOnDeviceModel,OnDeviceModelBackgroundDownload"
    )
    options.add_argument("--disable-component-update")
    options.add_argument("--disable-background-networking")
    return options
```

`_chrome_options()` imports `ChromiumOptions` locally, inside its own body, rather than reusing
`_open_browser()`'s `try/except ImportError` block — this keeps `_chrome_options()` independently
callable (and unit-testable) without going through `_open_browser()`'s async retry flow.
`ChromiumOptions` is part of the same `pydoll-python` package as `Chrome`, so no new dependency and
no new failure mode is introduced; if pydoll isn't installed, `_chrome_options()` simply isn't reached
before `_open_browser()`'s own import already raised the `ImportError` from D3.

Alternatives considered:
- **Inline the `ChromiumOptions()` construction directly in `_start()`** — rejected: harder to unit
  test in isolation; a dedicated helper lets a unit test assert the exact flag list without mocking
  the full async Chrome-start/retry flow.
- **Make the flags configurable via `tools.whiteboard.*` config** — rejected as unnecessary scope
  expansion; the report's fix is unconditional (these flags should always be on — they only disable
  unwanted background behavior, never something a user would want re-enabled), and no config
  mechanism was requested by the maintainer ruling.

### D5: Doc guidance for external chrome-devtools/playwright MCP servers

Report item 4a also asks for the same suppression-flag guidance to be surfaced for users who
configure their *own* external `chrome-devtools` or `playwright` MCP server (used by the `chrome_util`
/ `play_util` packs respectively) — those servers drive a real Chrome/Chromium instance the same way
pydoll does, and are equally exposed to the same background-download behavior if launched without
these flags. This is documentation only (no OneTool code touches those external servers' launch
config): add a short note to `docs/reference/tools/chrome-util.md` and
`docs/reference/tools/play-util.md`, in each file's `## Requires` section, listing the same three
flags as recommended launch arguments for the external server.

## Implementation guardrails

- **No compatibility shims.** The `whiteboard` extra is deleted, not deprecated, not aliased. Do not
  add a `whiteboard = ["onetool-mcp[util]"]` re-export group "just in case" — V3 is a breaking window
  and the report explicitly says "no shim."
- **No stubbing or TODO-deferral.** If `uv lock` cannot run in the implementation environment (e.g. no
  network access to PyPI/the package index), STOP and report that specifically — do not leave
  `uv.lock` stale and mark the task done anyway. A stale lock is a real regression for
  `uv sync --locked` / `just install-locked`.
- **Every code task ships with a test.** The `Chrome(options=...)` change needs a unit test (see
  tasks.md group 3) marked `@pytest.mark.unit`. The pyproject/doc-only tasks are verified by `rg`
  checks instead of new tests (no behavior to unit-test in a TOML edit or a markdown table edit), but
  those `rg` checks MUST actually be run — do not just eyeball the diff.
- **`just check` must pass before the change is considered complete.** This runs lint + typecheck +
  test with `--all-extras`, so `pydoll-python` will be installed in the dev/test environment
  regardless of which extra it's nominally under — `just check` passing does NOT by itself prove the
  extras restructure is correct. The `rg` checks and the fresh-install check (tasks.md Verification
  group) are what prove the extras contract; `just check` proves nothing broke functionally.
- **Every listed `rg` acceptance command that must return empty MUST actually be run**, and its actual
  (not assumed) output checked, before checking off the corresponding task.
- **Anchor drift**: file:line anchors in this design and in tasks.md were verified at
  `main`@`151a52b3` (2026-07-04). If a `Read`/`Grep` at implementation time shows different line
  numbers, use the current content match (function/block shown verbatim above) as the source of
  truth, make the edit at the correct location, and note the drift in the task's completion notes —
  do not silently edit the wrong lines or skip the task because the line number didn't match.

## Risks / Trade-offs

- [Deleting `[whiteboard]` breaks any user's pinned install command referencing it] → Mitigation:
  intentional, V3 breaking window; documented in proposal.md Impact as the migration note (install
  `[util]` or `[all]` instead); `p33-release-cut` surfaces this in the release changelog.
- [Chrome launch flags could theoretically change pydoll/Chrome CDP behavior in some environment where
  these flags aren't recognized] → Mitigation: all three flags are long-standing, well-documented
  Chromium command-line switches (`--disable-features=...`, `--disable-component-update`,
  `--disable-background-networking`); unrecognized Chromium flags are ignored by Chrome at startup
  rather than causing a launch failure, so this is low-risk even on older Chrome versions.
- [`otdev`/`[util]` cross-grouping (D2) is a minor ongoing consistency wrinkle] → Mitigation: explicitly
  accepted and documented as a rejected-for-V3 alternative (option (b), the module move) so it isn't
  rediscovered as a "bug" later; tracked as future work, not a defect of this change.
- [`uv.lock` regeneration could pull in unrelated dependency bumps if run against a newer index state
  than expected] → Mitigation: run `uv lock` (not `uv lock --upgrade`), which only re-resolves what's
  necessary for the `pyproject.toml` diff; review the resulting `uv.lock` diff and confirm it touches
  only `pydoll-python`'s `extra ==` marker (and the removed `whiteboard` extra group metadata), not
  unrelated package versions. If it touches more, STOP and report rather than accepting an
  unreviewed bulk lock update — that's out of scope for this change (dependency refresh is
  `p32-dependency-refresh`'s job).
