# Design — Whiteboard Runtime Hardening

## Context

The whiteboard pack lives in `src/otdev/tools/excalidraw.py` (~2 730 lines, pack `whiteboard`, aliases `wb`/`excalidraw`) with helpers in `src/otdev/tools/_excalidraw/` (`ops.js`, `bootstrap.js`, `session.py`, `renderers.py`, `dsl-reference.md`). The browser is pydoll-driven Chrome over CDP; JS assets are injected via `_browser_evaluate(_load_js(...))` (`excalidraw.py:71`, `:215`), which bypasses page CSP.

Current state (verified post-46ee09da):

- **`board=` coverage is partial.** `draw` (`:1003`), `erase` (`:1475`), `share` (`:1875`), `clear` (`:1972`), `layout` (`:2070`), `screenshot` (`:2582`) accept `board=` and pass it to `_session.load/save/clear_board`. `note` (`:1283`), `embed_dsl` (`:1427`), `save` (`:1574`), `load` (`:1628`), `sync` (`:1701`), `style` (`:1755`), `read_scene` (`:1823`) call `_session.load()`/`_session.save(state)` with no board — they always hit the CWD-keyed default board.
- **ELK from CDN.** `_ELK_CDN = "https://unpkg.com/elkjs@0.11.0/lib/elk.bundled.js"` (`:2062`); the layout JS appends a `<script src=CDN>` tag if `typeof ELK === 'undefined'` (`:2313-2322`).
- **`layout()` is ~460 lines** (`:2070`–`:2530`): validation, scene read, group/selection resolution, ELK graph build, boundary-edge bookkeeping, ELK run, node/text patching, boundary-arrow endpoint repositioning, subgraph bbox recompute, session write-back, fit.

Packaging: hatch `packages = ["src/otdev", ...]` ships non-Python assets in package dirs (ops.js already ships).

## Goals / Non-Goals

**Goals:**

- `board=` accepted by all 13 board-touching tools with uniform, backward-compatible semantics.
- `layout()` works with zero network access: ELK bundled with the pack.
- `layout()` decomposed into testable helpers with byte-identical observable behavior.

**Non-Goals:**

- Bugs B1–B5 (landed in 46ee09da).
- Headless browser mode — explicitly out of scope for this change; the "advertised headless mode" premise from the original issue is stale (no headless mention remains in pack code, spec, or docs).
- Error-channel unification (`read_scene` raises vs. others returning strings) and docstring naming drift.
- Multi-board canvas multiplexing (one live canvas at a time remains the model).
- Upgrading elkjs beyond 0.11.0 (pin the version currently used from CDN).

## Decisions

### D1 — `board=` semantics: "None = exactly today's behavior; explicit = operate against that board"

Uniform rule: state reads/writes go to `_session.load(board)` / `_session.save(state, board)`. For tools that read the **live canvas**, an explicit `board=` first rerenders that board's state onto the canvas (the established `screenshot()`/`share()` pattern: load → `_ensure_ready()` → `_rerender_from_state(state)`); `board=None` leaves the canvas untouched so existing call flows are unaffected.

| Tool | `board=` effect |
|---|---|
| `note(input=, background=, board=)` | Load/save named board state; placement uses that board's `canvas_max_y`; canvas push unchanged. |
| `embed_dsl(board=)` | DSL built from `_build_dsl(_session.load(board))`. |
| `save(file=, board=)` | `__otDSL` built from named board's state; when `board` is explicit, rerender that board before snapshotting the scene. `board=None`: snapshot live canvas as today. |
| `load(file=, board=)` | Restored state written via `_session.save(new_state, board)`. |
| `sync(board=)` | Synced state written via `_session.save(new_state, board)`. |
| `style(ids=, style=, board=)` | Explicit `board`: rerender it first, then apply visual styling. `None`: style live canvas as today (no rerender — a rerender would clobber prior visual-only styling). |
| `read_scene(info=, board=)` | Explicit `board`: rerender it first, then report. `None`: report live canvas as today. |

Board-name validation stays in `_session.session_path()` (raises `ValueError` on invalid names — existing behavior, applies automatically to the new parameters).

*Alternative rejected*: a module-level "current board" pointer set by `open()` — larger behavioral change, breaks the stateless-per-call model of the file-backed store.

### D2 — Vendor ELK: committed asset, CDP injection, no CDN path

- Commit `src/otdev/tools/_excalidraw/elk.bundled.js` — elkjs **0.11.0** `lib/elk.bundled.js` taken verbatim from the npm tarball (`npm pack elkjs@0.11.0`), ~1.4 MB. Commit `src/otdev/tools/_excalidraw/ELK_LICENSE.txt` (EPL-2.0 text + provenance header: package, version, source URL).
- Loading: a cached module-level loader (like `_load_js`, but the bundle is not a function expression — separate `_elk_bundle()` helper with its own cache). Before running the layout JS, Python checks `typeof window.ELK`; if undefined, inject via `_browser_evaluate` wrapping the bundle in a function body: elkjs's UMD assigns `window.ELK` explicitly, so function-scope evaluation is safe. Return `typeof window.ELK !== 'undefined'` and fail with a clear `"Error: ELK bundle injection failed"` string if false. The old `sc.src = CDN` block and `_ELK_CDN` constant are deleted.
- CDP `Runtime.evaluate` bypasses page CSP (same channel that already injects `ops.js`), so no inline-`<script>` CSP risk.
- Packaging: hatch ships all files under `src/otdev`; no pyproject change expected (verify wheel content in tasks).

*Alternatives rejected*: `<script textContent>` injection (subject to page CSP); keeping the CDN as fallback (reintroduces the network path and a silent supply-chain vector); downloading at install time (breaks offline installs, adds build machinery).

### D3 — Decompose `layout()`: pure computation helpers in `_excalidraw/layout.py`

New module `src/otdev/tools/_excalidraw/layout.py` containing **pure functions over plain dicts** (no pydoll, no browser I/O — unit-testable without mocks):

- `resolve_selection(scene) -> tuple[set[str], bool]` — selected element/group resolution.
- `build_elk_graph(scene, selection, params) -> ElkBuild` — returns a small dataclass: `graph` (ELK JSON), `elem_to_elk`, `elk_node_set`, `scene_edge_map`, `boundary_edges`, `offset_x/offset_y`, group membership maps. Encapsulates node/group sizing, eligible-edge filtering, boundary-edge capture, and the layered/stress option assembly (`_ELK_*` constant tables move here).
- `build_node_patches(elk_result, build, scene) -> list[dict]` — node + bound-text position patches, group member translation.
- `build_boundary_arrow_patches(build, positions, direction) -> list[dict]` — per-edge containment sides and endpoint ordering (the B1 fix lives here; keep its per-edge `src_in`/`dst_in` locals).
- `build_subgraph_updates(...)` — subgraph bbox recompute inputs.
- `writeback_positions(layout_state, positions, ...) -> None` — mutates the state dict (`x`/`y`, `canvas_max_y`) for `_session.save`.

`excalidraw.py:layout()` keeps: parameter validation, `LogSpan`, `_ensure_ready()`, the scene-read JS eval, ELK-run JS eval (now against the vendored bundle per D2), `_js_patch_elements` calls, `arrow_type` patching, `fit()`, and the return-string assembly. Target: `layout()` body under ~120 lines of orchestration.

**No behavior change**: same return strings, same patch payloads, same write-back. The existing layout tests in `tests/unit/tools/test_excalidraw.py` must pass unmodified; new unit tests may target the pure helpers directly.

*Alternative rejected*: nested closures inside `layout()` — no testability gain, file stays monolithic.

## Risks / Trade-offs

- [~1.4 MB `Runtime.evaluate` payload could hit pydoll/CDP message limits] → verified once per page load only (guarded by `typeof window.ELK`); if a limit is hit, fall back to chunked accumulation into a `window.__elkSrc` string then a single `eval` — decided at implementation time, spec only requires "no network fetch".
- [Vendored bundle drifts from upstream / license compliance] → provenance header + EPL-2.0 license file; version pinned to the exact CDN version used today (0.11.0), so behavior is unchanged.
- [Refactor regression in layout()] → helpers are extracted mechanically, existing tests run unmodified, and the diff is reviewable because computation moves out of the browser-I/O path.
- [`board=` rerender on style/read_scene clobbers un-persisted visual styling] → mitigated by the "None = no rerender" rule; documented in docstrings ("explicit board= rerenders that board's persisted state").

## Migration Plan

Purely additive: `board=None` defaults reproduce current behavior exactly. No data migration (session file schema untouched). Rollback = revert the commit; the vendored asset is self-contained.

## Open Questions

None — all decisions above are resolved; the only implementation-time choice is the chunked-injection fallback in D2, which does not affect observable behavior.
