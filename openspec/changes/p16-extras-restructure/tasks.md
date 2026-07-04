## 1. Extras restructure (`pyproject.toml`)

Current state (verify with `rg -n "^util = \[|^dev = \[|^scrape = \[|^whiteboard = \[|^all = " pyproject.toml` before editing — if line numbers below have drifted from `main`@`151a52b3`, use this block's *content* as the anchor, not the stale numbers, and note the drift):

```toml
util = [                                       # pyproject.toml:54-65
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
...
scrape = [                                     # pyproject.toml:76-78
    "crawl4ai>=0.8.6",
]
whiteboard = [                                 # pyproject.toml:79-81
    "pydoll-python>=2.22.1",
]
all = ["onetool-mcp[util,dev]"]                # pyproject.toml:82
```

- [x] 1.1 Insert `"pydoll-python>=2.22.1",       # Chrome CDP driver for whiteboard pack` into the
      `util` list (`pyproject.toml:54-65`) — insert it alphabetically between `"pathspec>=1.1.1",` and
      `"pymupdf>=1.27.2.3",` to match the existing alphabetical ordering of that stretch of the list.
- [x] 1.2 Delete the entire `whiteboard = [ "pydoll-python>=2.22.1", ]` block (`pyproject.toml:79-81`),
      including its blank-line separation from the surrounding blocks.
- [x] 1.3 Confirm `all = ["onetool-mcp[util,dev]"]` (`pyproject.toml:82`) is unchanged — do NOT add
      `whiteboard` or `scrape` into this list. `scrape` (`crawl4ai`, now at `pyproject.toml:76-78`,
      shifted up if line numbers moved) stays a standalone opt-in extra, untouched by this change.
- [x] 1.4 Run `rg -n "whiteboard" pyproject.toml` and confirm it returns NO matches (no leftover
      `whiteboard` extra name, no stray reference anywhere else in the file — check the `pydoll:
      Requires pydoll Chrome CDP automation` pytest marker line too; it must NOT be touched or
      renamed, it only mentions "pydoll" not "whiteboard").

## 2. Lockfile regeneration

- [x] 2.1 Run `uv lock` (NOT `uv lock --upgrade`) to regenerate `uv.lock` from the edited
      `pyproject.toml`.
- [x] 2.2 Inspect the `uv.lock` diff (`git diff uv.lock`) and confirm it touches ONLY:
      `pydoll-python`'s `extra ==` marker (moves from `'whiteboard'` to `'util'`) and the removal of
      the `whiteboard` extra group's metadata. If the diff includes unrelated dependency version
      bumps, STOP and report — do not accept an unreviewed bulk lock update as part of this change
      (that's `p32-dependency-refresh`'s scope).
- [x] 2.3 If `uv lock` cannot run (e.g. no package-index network access in the implementation
      environment), STOP and report this explicitly. Do not mark this task done with a stale
      `uv.lock` — `uv sync --locked` / `just install-locked` will silently keep resolving the old
      `whiteboard`-gated `pydoll-python` marker otherwise.

## 3. Excalidraw code changes (`src/otdev/tools/excalidraw.py`)

Current state of `_open_browser()` (`src/otdev/tools/excalidraw.py:99-132`):

```python
def _open_browser() -> None:
    """Launch pydoll browser, open tab, navigate to excalidraw.com."""
    global _browser, _tab
    try:
        from pydoll.browser import Chrome
        from pydoll.exceptions import NoValidTabFound
    except ImportError:
        raise ImportError(
            "pydoll-python is required for whiteboard. "
            "Install with: pip install 'onetool-mcp[whiteboard]'"
        ) from None

    async def _start() -> tuple[Any, Any]:
        # Chrome's initial page target may not be registered immediately after the
        # CDP endpoint comes up. Retry up to 3 times with a 1-second gap so the
        # race window doesn't permanently block the first cold start.
        last_exc: Exception = RuntimeError("browser start failed")
        for attempt in range(3):
            if attempt > 0:
                await asyncio.sleep(1)
            b = Chrome()
            try:
                t = await b.start()
                return b, t
            except NoValidTabFound as exc:
                last_exc = exc
                with contextlib.suppress(Exception):
                    await b.stop()  # type: ignore[no-untyped-call]
        raise last_exc

    b, t = _run(_start())
    _browser = b
    _tab = t
    _browser_navigate("https://excalidraw.com")
```

- [x] 3.1 Change the `ImportError` message at `src/otdev/tools/excalidraw.py:107-108` from
      `"Install with: pip install 'onetool-mcp[whiteboard]'"` to
      `"Install with: pip install 'onetool-mcp[util]'"`. The message prefix
      (`"pydoll-python is required for whiteboard. "`) is unchanged.
- [x] 3.2 Do NOT add `ChromiumOptions` to `_open_browser()`'s existing
      `try: ... except ImportError:` import block (`src/otdev/tools/excalidraw.py:102-104`, importing
      `Chrome` and `NoValidTabFound`) — `_chrome_options()` (task 3.3) does its own local import of
      `ChromiumOptions`, so no change is needed here beyond the message text from task 3.1.
- [x] 3.3 Add a module-level helper function `_chrome_options() -> Any`, defined just above
      `_open_browser()` (around line 98), that constructs and returns a `ChromiumOptions` instance
      with exactly these three arguments added via `.add_argument(...)`:
      - `--disable-features=OptimizationGuideOnDeviceModel,OnDeviceModelBackgroundDownload`
      - `--disable-component-update`
      - `--disable-background-networking`

      `_chrome_options()` SHALL take no arguments and SHALL do its own local
      `from pydoll.browser.options import ChromiumOptions` import inside its body (matching the
      existing pattern in this file where `_open_browser()` itself locally imports `Chrome` and
      `NoValidTabFound` rather than importing pydoll at module level). This makes `_chrome_options()`
      directly callable and unit-testable on its own, without needing to go through
      `_open_browser()`'s try/except or its async retry loop.
- [x] 3.4 Change `b = Chrome()` (`src/otdev/tools/excalidraw.py:119`, inside the `for attempt in
      range(3):` retry loop) to `b = Chrome(options=_chrome_options())`, so every retry attempt —
      not just the first — launches with the suppression flags.
- [x] 3.5 Re-read the edited `_open_browser()` function and confirm there is no remaining code path
      that constructs `Chrome()` with zero arguments anywhere in `src/otdev/tools/excalidraw.py`
      (`rg -n "Chrome\(\)" src/otdev/tools/excalidraw.py` must return no matches).

## 4. Tests for the Chrome launch flags

- [x] 4.1 In `tests/unit/tools/test_excalidraw.py`, add a unit test (marked `@pytest.mark.unit` and
      `@pytest.mark.tools` per this file's existing marker convention) that calls
      `otdev.tools.excalidraw._chrome_options()` directly and asserts the returned object's
      `.arguments` list is exactly
      `["--disable-features=OptimizationGuideOnDeviceModel,OnDeviceModelBackgroundDownload",
      "--disable-component-update", "--disable-background-networking"]` (order-sensitive is fine
      since the helper always adds them in this order; if order-insensitive assertion is preferred,
      assert set equality instead — either is acceptable as long as all three exact strings are
      checked).
- [x] 4.2 In `tests/unit/tools/test_excalidraw.py`, add a second unit test that exercises
      `otdev.tools.excalidraw._open_browser()` end-to-end with `pydoll.browser.Chrome` mocked (patch
      target: `"pydoll.browser.Chrome"`, matching how `_open_browser()` imports it via
      `from pydoll.browser import Chrome`), asserting that `Chrome` was called with an `options=`
      kwarg whose `.arguments` contains all three suppression flags. Mock `Chrome(...).start()` as an
      `AsyncMock` returning a mock tab object whose `.go_to` is also an `AsyncMock` (needed because
      `_open_browser()` calls `_browser_navigate("https://excalidraw.com")` after `_start()`
      succeeds, which calls `_tab.go_to(url=url)`). This test proves the flags actually reach the real
      `Chrome(...)` call site, not just the helper in isolation.
- [x] 4.3 Run `uv run pytest -m "unit and tools" tests/unit/tools/test_excalidraw.py -k chrome_option`
      (adjust the `-k` filter to match your actual test names) and confirm both new tests pass.

## 5. Documentation — extras contract

- [x] 5.1 `docs/reference/tools/whiteboard.md:58` — change
      `` - `onetool-mcp[whiteboard]` extra (provides `pydoll-python`; not included in `[all]`) ``
      to
      `` - `onetool-mcp[util]` extra (provides `pydoll-python`; included in `[all]`) ``.
- [x] 5.2 `README.md` — in the tools table, the `whiteboard` row (currently at `README.md:159`:
      `` | `whiteboard`  | `open`, `draw`, `screenshot`, `save`           | `[dev]`  | Live Excalidraw canvas         | ``)
      — change the extras column from `` `[dev]` `` to `` `[util]` ``.
- [x] 5.3 `docs/learn/installation.md` — in the "Optional Tool Packs" table
      (`docs/learn/installation.md:51-52`):
      - Remove `whiteboard` from the `[dev]` row's tool list (currently: `` `[dev]` | `chrome_util`,
        `context7`, `db`, `diagram`, `package`, `play_util`, `ripgrep`, `webfetch`, `whiteboard` | ``).
      - Add `whiteboard` to the `[util]` row's tool list (currently: `` `[util]` | `brave`, `convert`,
        `excel`, `file`, `ground`, `knowledge`, `mem`, `tavily` | ``), keeping alphabetical order.
- [x] 5.4 `docs/reference/tools/index.md` — in the "Optional Extras" table
      (`docs/reference/tools/index.md:17-18`):
      - Remove `whiteboard` from the `[dev]` row's tool list.
      - Add `whiteboard` to the `[util]` row's tool list, keeping alphabetical order.
      Also in the per-tool table further down (`docs/reference/tools/index.md:55`, the
      `` | [**WB (Whiteboard)**](whiteboard.md) | `[dev]` | ... `` row) — change the extras column
      from `` `[dev]` `` to `` `[util]` ``.
- [x] 5.5 `docs/llms.txt:53` — change `` | `whiteboard` | `[dev]` | Live whiteboard using Excalidraw...``
      to use `` `[util]` `` instead of `` `[dev]` ``.
- [x] 5.6 Run `rg -n "\[whiteboard\]" src/ docs/ README.md` and confirm it returns NO matches (the
      only prior occurrence, `docs/reference/tools/whiteboard.md:58`, was fixed in task 5.1).
- [x] 5.7 Do NOT edit `CHANGELOG.md` or `docs/learn/whats-new-v2.md` — both are historical release
      records describing extras contracts that were accurate at the time of those past releases. The
      V3 breaking-change note lives in this change's `proposal.md` Impact section; folding it into a
      new `CHANGELOG.md` entry is `p33-release-cut`'s job, not this task group's.

## 6. Documentation — external MCP server launch-flag guidance

- [x] 6.1 In `docs/reference/tools/chrome-util.md`, under the `## Requires` section (currently just
      the line: `- A Chrome DevTools-compatible MCP server must be enabled. By default this pack uses
      \`chrome_devtools\`; pass \`server="..."\` to target a compatible server configured under
      another name.`), add a short note recommending the same three Chrome launch flags used by the
      whiteboard pack when the user configures their own external `chrome-devtools` MCP server:
      `--disable-features=OptimizationGuideOnDeviceModel,OnDeviceModelBackgroundDownload`,
      `--disable-component-update`, `--disable-background-networking` — explain in one sentence why
      (avoids an unexpected ~4GB on-device Gemini Nano model download / background networking the
      first time Chrome is driven via CDP).
- [x] 6.2 Make the equivalent addition to `docs/reference/tools/play-util.md`'s `## Requires` section
      for users configuring an external `playwright` MCP server.

## 7. Verification

Run each command below and confirm the stated result before considering this change complete. Do not
mark a task done based on "I edited the file" — run the command and read its actual output.

- [x] 7.1 `rg -n "whiteboard" pyproject.toml` → NO matches (task 1.4).
- [x] 7.2 `rg -n "\[whiteboard\]" src/ docs/ README.md` → NO matches (task 5.6).
- [x] 7.3 `git diff uv.lock` → touches only `pydoll-python`'s extra marker + removed `whiteboard`
      group metadata (task 2.2).
- [ ] 7.4 Fresh-install check, simulating `uv pip install onetool-mcp[all]` / `[util]` against an
      unreleased local build (the package is not yet published to PyPI at V3 implementation time, so
      install from a local wheel instead of the real registry):
      ```bash
      uv build
      uv venv /tmp/p16-verify --python 3.12
      WHEEL=$(ls dist/onetool_mcp-*-py3-none-any.whl | tail -1)
      uv pip install --python /tmp/p16-verify/bin/python "${WHEEL}[util]"
      /tmp/p16-verify/bin/python -c "import pydoll; from otdev.tools import excalidraw; print('whiteboard import OK')"
      ```
      → prints `whiteboard import OK` with no `ImportError`. Repeat with `[all]` instead of `[util]`
      to confirm the same result via the convenience extra.
- [x] 7.5 `uv run pytest -m "unit and tools" tests/unit/tools/test_excalidraw.py` → all tests pass,
      including the two new tests from group 4.
- [x] 7.6 `uv run python scripts/check_docs_registry.py` → passes (repo doc-registry gate; this
      change doesn't touch tool signatures, but run it to confirm the doc edits in group 5/6 didn't
      break the generated-content markers in `docs/reference/tools/whiteboard.md`,
      `chrome-util.md`, or `play-util.md`).
- [x] 7.7 `just check` → passes (lint + typecheck + test, `--all-extras`). Note per design.md: this
      does NOT by itself validate the extras contract (it installs `--all-extras` regardless of which
      extra `pydoll-python` nominally belongs to) — it validates that nothing else broke.
