# React Flow architecture and ZenUML sequence PoC

Status: deferred post-V2 research. Report v2 does not implement native sequence
diagrams; it displays externally generated sequence diagrams as validated,
presentation-only SVG attachments. The spike is preserved for possible work
after V2 is complete and is not a V2 runtime or contract dependency.

An isolated visual and interaction prototype produced during Report v2
research. It uses React Flow for the C4 architecture canvas and compares native
OneTool SVG with ZenUML's native SVG sequence renderer inside the same
Archify-inspired frame.

## Run

```bash
npm install
npm run dev
```

Then open the local URL printed by Vite.

Run the bounded spike checks with:

```bash
npm run check
```

## Demonstrated behavior

- C4 container map with explicit custom nodes, labelled relationships,
  hierarchy/trust boundaries, minimap, pan, zoom, fit, and search.
- Semantic and relationship passports for nodes, edges, participants, and
  sequence messages.
- PATH, MAP, and LENS modes with route probes and contextual dimming.
- Movable semantic passports and route probes: drag the grip, use arrow keys
  (Shift for larger steps), or double-click the grip to reset the panel.
- Native and ZenUML temporal sequence rendering, message stepping, and overview
  radar through one canonical fixture.
- A 12-participant/100-message ZenUML stress fixture with nested `alt`/`loop`
  fragments, sync/async calls, returns, activations, and a long label.
- Lazy ZenUML loading, render timing, output bounds, and live canonical-ID
  mapping counts.
- Light/dark themes, responsive layout, keyboard-operable controls, copy-link
  fragments, and full-screen mode.

## Bounded ZenUML spike

The spike uses only the documented `@zenuml/core` `renderToSvg()` API and the
documented `@zenuml/core/parser` entry point. It does not import renderer source
or geometry internals.

| Gate | Result |
| --- | --- |
| Checkout DSL parses | Pass |
| 12 participants / 100 messages parse | Pass |
| Nested `alt` / `loop`, sync, async, returns, and activations render | Pass |
| Checkout canonical participant/message annotation | Pass: 6/6 and 9/9 |
| Stress canonical participant/message annotation | Pass: 12/12 and 100/100 |
| Pointer and keyboard message selection update passport/step | Pass |
| Direct selection reveals step 100 in the scroll viewport | Pass |
| Initial shell avoids eagerly loading ZenUML | Pass |
| Stable public semantic SVG IDs | Fail: supplied by the OneTool adapter |
| Long-label presentation | Needs work: no attractive wrapping in the stress case |
| Screen-reader equivalent | Not provided by SVG; any future native viewer would need an accessible alternative independent of rendered SVG structure |

Measured from the local production build on 2026-08-11:

- shell JavaScript: 415.98 kB minified / 131.85 kB gzip;
- lazy ZenUML chunk: 3,458.47 kB minified / 869.00 kB gzip;
- stress SVG bounds: 1,577 × 3,615;
- local development render observations: checkout approximately 1–3 ms and
  stress approximately 4–63 ms after the module is available. These timings are
  indicative, not a benchmark result.

Canonical message hooks are added after rendering by matching ZenUML's message
and return label classes within their preserved per-kind order. This handles
duplicate labels, but the class structure is a renderer compatibility boundary,
not a stable semantic API. The pinned 4.2.0 grammar also uses `p1 as "Label"`
for explicit participants; prefixing that declaration with the documented
`participant` keyword creates an unwanted literal participant in this renderer.

The result keeps ZenUML interesting for a future native sequence capability, but
does not create or justify a V2 `SequenceDocument`, `SequenceScene`, runtime
adapter, renderer dependency, or semantic DOM contract. For V2, a ZenUML SVG is
handled like any other validated presentation-only diagram attachment.

The sample data and geometry are static. This PoC does not change or replace the
production architecture tool, renderer, layout engine, schemas, or specs.
