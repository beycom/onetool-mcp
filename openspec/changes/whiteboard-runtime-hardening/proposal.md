# Whiteboard Runtime Hardening

## Why

The whiteboard pack (`src/otdev/tools/excalidraw.py`, pack `whiteboard`, aliases `wb`/`excalidraw`) has three deferred runtime gaps left over after the B1–B5 bug fixes landed in 46ee09da: the `board=` parameter is supported by only 6 of the 13 board-touching tools (agents cannot reliably work with named boards), `layout()` fetches ELK.js from the unpkg CDN at runtime (network dependency, supply-chain exposure, offline failure), and `layout()` is a ~460-line monolith that resists safe modification.

## What Changes

- **`board=` parameter coverage**: add `board: str | None = None` to `note()`, `save()`, `load()`, `sync()`, `style()`, `read_scene()`, and `embed_dsl()`, matching the existing semantics of draw/erase/clear/layout/screenshot/share: state tools read/write the named board's session file; browser tools that are given an explicit `board=` rerender that board's state onto the canvas first.
- **Vendor ELK.js**: ship `elkjs@0.11.0` (`elk.bundled.js`, EPL-2.0, with license file) inside `src/otdev/tools/_excalidraw/` and inject it over CDP instead of loading `https://unpkg.com/...` at runtime. `layout()` performs no CDN fetch. Remove `_ELK_CDN`.
- **Decompose `layout()`**: split the ~460-line function into cohesive helpers in a new `src/otdev/tools/_excalidraw/layout.py` module (scene read, ELK graph build, ELK run, position apply, boundary-arrow repositioning, state write-back). No behavior change — pure refactor, verified by the existing layout test suite.

Not in scope: bugs B1–B5 (already landed in 46ee09da), headless browser mode (explicitly out of scope; the "advertised headless mode" premise from the original issue is stale — no headless mention remains in pack code, spec, or docs), error-channel unification, docstring naming drift.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `otdev/tool-excalidraw` (main spec: `openspec/specs/otdev/tool-excalidraw/spec.md`; delta at `specs/otdev/tool-excalidraw/spec.md`): (1) `board=` requirement extended to note/save/load/sync/style/read_scene/embed_dsl with defined per-tool semantics; (2) the "Graph layout via ELK.js" requirement changes from "inject `elkjs@0.11.0` from CDN" to "inject the bundled `elkjs@0.11.0` asset — no network fetch". The `layout()` decomposition is implementation-only (no spec delta).

## Impact

- **Code**: `src/otdev/tools/excalidraw.py` (7 tool signatures, `layout()` shrinks to orchestration), new `src/otdev/tools/_excalidraw/layout.py`, new vendored assets `src/otdev/tools/_excalidraw/elk.bundled.js` (~1.4 MB, committed) + `ELK_LICENSE.txt`.
- **Config**: none.
- **Dependencies**: none added; removes the runtime dependency on unpkg.com availability.
- **Tests**: `tests/unit/tools/test_excalidraw.py` — new board-parameter tests; existing layout tests guard the refactor.
- **Docs/spec**: `openspec/specs/otdev/tool-excalidraw/spec.md` requirements updated per the delta spec.
