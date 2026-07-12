# Tasks — whiteboard-runtime-hardening

## 1. Vendor ELK (unblocks layout work; smallest independent slice)

- [x] 1.1 Fetch `elkjs@0.11.0` `lib/elk.bundled.js` from the npm tarball (`npm pack elkjs@0.11.0`) and commit it verbatim as `src/otdev/tools/_excalidraw/elk.bundled.js`
- [x] 1.2 Add `src/otdev/tools/_excalidraw/ELK_LICENSE.txt` with the EPL-2.0 text and a provenance header (package `elkjs`, version `0.11.0`, source URL)
- [x] 1.3 In `src/otdev/tools/excalidraw.py`: add a cached `_elk_bundle()` loader (importlib.resources, module-level cache; do not reuse `_load_js` — the bundle is not a function expression)
- [x] 1.4 Replace the CDN `<script src>` block in the layout JS (`excalidraw.py:2314-2322`) with a Python-side pre-step: check `typeof window.ELK`; if undefined, inject the bundle via `_browser_evaluate` (function-scope wrap; elkjs UMD assigns `window.ELK`), verify `window.ELK` is defined, return `"Error: ELK bundle injection failed — ..."` on failure
- [x] 1.5 Delete `_ELK_CDN` (`excalidraw.py:2062`) and update the `layout()` docstring ("Loads ELK.js from CDN" → bundled asset)
- [x] 1.6 Unit tests: injection guard (second `layout()` call does not re-inject given `window.ELK` defined), injection-failure error string, and assert no `unpkg` string remains in the module
- [x] 1.7 Verify packaging: `just build` (or `uv build`) and confirm `elk.bundled.js` + `ELK_LICENSE.txt` are inside the wheel's `otdev/tools/_excalidraw/`

## 2. board= parameter coverage

- [x] 2.1 `note()`: add `board: str | None = None`; use `_session.load(board)` / `_session.save(..., board)` (`excalidraw.py:1397,1414`); placement `_get_canvas_max_y()` stays canvas-based; docstring Args updated
- [x] 2.2 `embed_dsl()`: add `board=`; build DSL via `_build_dsl(_session.load(board))`
- [x] 2.3 `save()`: add `board=`; build `__otDSL` from `_session.load(board)`; when `board` is not None, `_rerender_from_state(_session.load(board))` after `_ensure_ready()` and before the scene snapshot (screenshot pattern, `excalidraw.py:2600-2606`)
- [x] 2.4 `load()`: add `board=`; write restored state via `_session.save(new_state, board)`
- [x] 2.5 `sync()`: add `board=`; write synced state via `_session.save(new_state, board)` (`excalidraw.py:1727`)
- [x] 2.6 `style()`: add `board=`; when not None, rerender that board first, then style the live canvas; when None, no rerender (unchanged)
- [x] 2.7 `read_scene()`: add `board=`; when not None, rerender that board first; when None, unchanged
- [x] 2.8 Update docstrings of all seven tools with a uniform `board:` Args line ("Named board to operate on. Defaults to the CWD-keyed board.")
- [x] 2.9 Unit tests: `note(board=)` and `sync(board=)` write to `{board}.json` not the default; `load(file=, board=)` targets the named board; `save(board=)`/`read_scene(board=)` trigger a rerender from the named board's state; omitted `board` byte-identical to previous behavior; invalid board name raises `ValueError`

## 3. Decompose layout()

- [x] 3.1 Create `src/otdev/tools/_excalidraw/layout.py` with pure helpers (no pydoll/browser imports): `resolve_selection()`, `build_elk_graph()` (returns an `ElkBuild` dataclass: graph, elem_to_elk, elk_node_set, scene_edge_map, boundary_edges, offsets, group maps), `build_node_patches()`, `build_boundary_arrow_patches()` (per-edge `src_in`/`dst_in` — preserve the B1 fix), `build_subgraph_updates()`, `writeback_positions()`; move the `_ELK_*` constant tables here (re-export from `excalidraw.py` if tests reference them)
- [x] 3.2 Rewrite `excalidraw.py:layout()` as orchestration only (validation, LogSpan, `_ensure_ready`, scene-read eval, ELK-run eval, `_js_patch_elements`, `arrow_type` patching, `fit()`, return string) delegating all computation to `_excalidraw.layout`; target ≤ ~120 lines; identical signature, return strings, and patch payloads
- [x] 3.3 Run the existing layout tests in `tests/unit/tools/test_excalidraw.py` UNMODIFIED and confirm they pass (behavior-preservation gate)
- [x] 3.4 Add direct unit tests for the pure helpers (no browser mocks): graph build with groups + selection, boundary-arrow patch sides for each direction, write-back mutation

## 4. Verification and close-out

- [x] 4.1 `uv run pytest -m "unit and tools"` green; `just lint` and `uv run mypy` clean on changed files
- [x] 4.2 Grep gate: no `unpkg`/`_ELK_CDN` references anywhere in `src/`; `grep -c "board: str | None" src/otdev/tools/excalidraw.py` covers all 13 tools
- [x] 4.3 Sync the delta spec into `openspec/specs/otdev/tool-excalidraw/spec.md` (opsx sync/archive flow) and update `dsl-reference.md`/docs if they mention the ELK CDN
