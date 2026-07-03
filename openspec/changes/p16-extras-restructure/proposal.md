## Why

`pyproject.toml` currently defines `all = ["onetool-mcp[util,dev]"]` (line 82), but the `whiteboard`
extra (`pydoll-python>=2.22.1`, lines 79-81) is standalone — NOT included in `[util]` or `[dev]`, and
therefore NOT included in `[all]`. `README.md:58` documents `uv tool install 'onetool-mcp[all]'` as
"everything" and `README.md:119` markets "Live Whiteboard" as a flagship feature, but the recommended
`[all]` install cannot actually run `whiteboard.open()` — it raises `ImportError` because
`pydoll-python` was never pulled in. A maintainer ruling (`wip/release-v3/release-v3-report-2.md`
R3 item 4) resolves this by folding `pydoll-python` into the `util` extra and deleting the standalone
`whiteboard` extra, so `[all]` (still `[util,dev]`) picks it up automatically.

That fix has a direct safety consequence (R3 item 4a): once whiteboard rides every `util`/`all`
install, its Chrome launch path becomes reachable from a plain recommended install. Today
`src/otdev/tools/excalidraw.py:119` calls `Chrome()` with no options, so pydoll drives the user's
real installed Chrome with zero suppression flags — a single `whiteboard.open()` can silently trigger
Chrome to background-download the ~4GB on-device Gemini Nano model plus unrelated background
networking. This must land in the same change as the extras move, not as a follow-up.

## What Changes

- **BREAKING**: Delete the standalone `whiteboard` optional-dependency group from `pyproject.toml`.
  There is no compatibility shim — `pip install 'onetool-mcp[whiteboard]'` will fail after this
  change (V3 is a breaking-changes window; the fix is to install `[util]` or `[all]` instead).
- Move `pydoll-python>=2.22.1` from the (deleted) `whiteboard` extra into the `util` extra. `all`
  (`= ["onetool-mcp[util,dev]"]`) is unchanged in text but now transitively includes `pydoll-python`,
  so `onetool-mcp[all]` and `onetool-mcp[util]` both make `whiteboard.*` importable.
  `onetool-mcp[scrape]` (`crawl4ai`) remains the one specialized extra that stays outside `[all]` —
  unaffected by this change.
  - `all` remains `["onetool-mcp[util,dev]"]` verbatim — no line edit here, only downstream effect.
- Update the `ImportError` install hint in `src/otdev/tools/excalidraw.py:107-108` from
  `pip install 'onetool-mcp[whiteboard]'` to `pip install 'onetool-mcp[util]'`.
- Regenerate `uv.lock` so the `pydoll-python` dependency's `extra ==` marker moves from `'whiteboard'`
  to `'util'` and the deleted extra group disappears from the lock metadata.
- Suppress Chrome's on-device Gemini Nano download and background networking when pydoll launches
  Chrome for the whiteboard pack: pass a `ChromiumOptions` with
  `--disable-features=OptimizationGuideOnDeviceModel,OnDeviceModelBackgroundDownload`,
  `--disable-component-update`, and `--disable-background-networking` to `Chrome(options=...)` at
  `src/otdev/tools/excalidraw.py:119`.
- Update every doc that names the `whiteboard` extra or lists whiteboard under `[dev]`/`[util]` to
  reflect the new extras contract: `README.md`, `docs/learn/installation.md`,
  `docs/reference/tools/index.md`, `docs/reference/tools/whiteboard.md`, `docs/llms.txt`.
- Add doc guidance (in `docs/reference/tools/chrome-util.md` and `docs/reference/tools/play-util.md`)
  recommending the same three Chrome suppression flags for users who configure their own external
  `chrome-devtools`/`playwright` MCP servers, since those tools drive a real Chrome instance the same
  way pydoll does.
- Historical `CHANGELOG.md` entries (v2.x and earlier) are NOT edited — they describe extras
  contracts that were true at the time of that release. The V3 breaking-change entry for the removed
  `[whiteboard]` extra is compiled into the release changelog by the `p33-release-cut` change, which
  aggregates breaking-change notes from all V3 changes; this proposal's Impact section is that note's
  source of truth for this change.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `otdev/tool-excalidraw`: adds two requirements — the `[util]` install extra contract (replacing the
  deleted `[whiteboard]` extra) and the Chrome launch suppression-flags requirement. Both are ADDED
  requirements (no existing requirement in `openspec/specs/otdev/tool-excalidraw/spec.md` currently
  covers install extras or launch flags), so no MODIFIED block is needed for this capability.

## Impact

- **Affected code**: `pyproject.toml` (extras), `uv.lock` (regenerated), `src/otdev/tools/excalidraw.py`
  (ImportError message + `Chrome()` launch options).
- **Affected docs**: `README.md`, `docs/learn/installation.md`, `docs/reference/tools/index.md`,
  `docs/reference/tools/whiteboard.md`, `docs/reference/tools/chrome-util.md`,
  `docs/reference/tools/play-util.md`, `docs/llms.txt`.
- **Affected tests**: `tests/unit/tools/test_excalidraw.py` (new test(s) for the Chrome launch
  options).
- **Dependencies**: no new PyPI dependency; `pydoll-python` simply changes which extra group owns it.
- **Breaking change / migration**: `pip install 'onetool-mcp[whiteboard]'` (or
  `uv tool install 'onetool-mcp[whiteboard]'`) will fail after this change — the extra no longer
  exists. Migration: install `[util]` (or `[all]`, which includes `[util]`) instead; no other action
  needed since the whiteboard *module* (`src/otdev/tools/excalidraw.py`) was never gated by the
  `whiteboard` extra itself (only its `pydoll-python` dependency was). This is recorded here as the
  breaking-changes/migration note for `p33-release-cut` to fold into the V3 `CHANGELOG.md` entry — do
  not edit `CHANGELOG.md` directly as part of this change.
- **Deliberately out of scope for V3 (rejected alternative, recorded per maintainer ruling)**: moving
  `src/otdev/tools/excalidraw.py` + `src/otdev/tools/_excalidraw/` + `tests/unit/tools/test_excalidraw.py`
  + `tests/otdev/integration/tools/test_excalidraw.py` from `otdev` (the `[dev]` package) to `otutil`
  (the `[util]` package) to fully align the `otdev↔dev` / `otutil↔util` naming convention with the new
  extras assignment. Rejected reason: functionally unnecessary — extras gate only PyPI dependency
  resolution, not which package directory a tool module lives in; the whiteboard module ships and
  loads regardless of which extra is installed, and errors gracefully (via the `ImportError` hint) if
  `pydoll-python` is absent. The cross-grouping (whiteboard code in `otdev`, its dependency in
  `[util]`) is accepted for V3 as a defensible minimal-scope outcome; the larger module move is
  deferred to a post-V3 change.
