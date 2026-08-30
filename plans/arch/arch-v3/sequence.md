# Sequence diagrams v3

Status: proposed (2026-08-25, user-directed). This document owns the sequence
aspect: authored sequence docs, their DSL, Python compilation, the renderer
decision, and the interaction contract. It reverses the report.md deferral
("no native renderer; SVG attachments only") — that verdict rejected
*third-party* renderers, and the 2026 re-survey below confirms none fits; the
native path it left open is what this document specs.

Sequence flows are documentation *about* the model, not part of it: they
reference entity and interface ids but live in their own text docs, may name
ad-hoc participants the model doesn't contain, and never affect resolution,
diff, or validation of the model itself.

## Source docs

Sequence flows are Markdown files in a `sequences/` directory beside the
canonical YAML — one flow per file, discovered by `arch.validate` /
`arch.generate` as `<model-dir>/sequences/*.md`. They are the only transport:
sequences are deliberately **not** carried by the Excel adapter or any other
tabular adapter (they are documents, not tables — index.md principle 4 does
not apply to them).

Shape of a flow doc:

````markdown
---
id: order-checkout          # required; id grammar; unique across all flow docs
name: Order checkout        # required
description: …              # optional
tags: [payments]            # optional
start_in: phase-2           # optional; inclusive interval over base,
end_in: phase-4             #   identical semantics to entity rows
---

participant customer
participant psp as External PSP

## Happy path

Optional prose — rendered as the scenario description.

```seq
customer ->> payments-api: Place order [i-0031]
payments-api ->> psp: Authorise card
psp -->> payments-api: Approved
payments-api -) event-bus: OrderPlaced
payments-api -->> customer: 202 Accepted
```

## Declined

```seq
customer ->> payments-api: Place order [i-0031]
payments-api ->> psp: Authorise card
alt Soft decline
  payments-api ->> psp: Retry authorisation
  divider delay: cooldown
  psp -->> payments-api: Approved
else Hard decline
  payments-api -x psp: Authorise card
  payments-api -->> customer: 402 Declined
end
```
````

- Each `##` heading is a **scenario** (happy path, error path, retry path,
  admin path, …); its id is the heading slug (lowercased, spaces → hyphens;
  must satisfy the id grammar; duplicate slugs in one doc are an error). A
  doc with no headings has one implicit scenario `main`.
- `participant` lines may appear at doc level (before the first heading,
  fenced or bare) or inside a scenario fence; declarations are doc-scoped.
  Column order = declaration order, then first appearance; the order is
  shared by every scenario in the doc so the reader keeps one mental map.

## DSL (inside ```seq fences)

**Base grammar: Mermaid sequence syntax, with arrows generalized so that
davidje13/SequenceDiagram's published arrow forms are equally valid**
(decided 2026-08-25) — one union grammar, so knowledge and snippets from
either tool paste straight in. No `sequenceDiagram` header line — the `seq`
fence type carries that.

Participants (declaration optional — see bare-name rule below):

| Line | Meaning |
| --- | --- |
| `participant <id>` | model-backed participant; `<id>` must resolve in systems / containers / components / code / users (error if declared and unresolved) |
| `participant <name> as <Label>` | ad-hoc participant (not in the model); label needs no quotes |
| `actor <name> as <Label>` | ad-hoc participant rendered with the person glyph |

A message line is `endpoint arrow endpoint` with an **optional** `: text`
label. Endpoints:

- a participant name, optionally prefixed `+` (open its activation bar) or
  `-` (close it);
- `[` or `]` — the left / right diagram edge (**external** messages, any
  arrow form, either direction); renders against an edge stub, pairing
  with the canvas boundary-stub concept;
- `...id` — **deferred async delivery**: send now (`a -) ...req: text`),
  arrival later (`...req -) b`) — expresses *crossing* messages; the
  halves pair by id, completion after the send in the same scenario.

**Arrows are compositional**, not a token list: an optional left head
(`<` / `<<`), a line — `-` solid, `--` dashed, `~` wavy — and an optional
right head (`>` / `>>` / `)` / `x`). Every form both grammars publish is
therefore legal: `->`, `->>`, `-->`, `-->>`, `-)`, `-x`, `--x`, `<-`,
`<--`, `<->`, `<-->`, `<<-->`, `~>`, unlabeled arrows, `Bar -> Bar`
self-messages. At least one head is required (a headless line is a parse
error), and an `x` head may not combine with a left head — lost messages
are directional (2026-08-25, pinned by the parser vectors).

**Kind derivation** (first match wins; drives rendering and validation):

1. any `x` head → **lost / failed** (cross head — error paths);
2. a `)` head or `~` line → **async** (event, queue, fire-and-forget);
3. dashed `--` line → **reply** / return;
4. otherwise → **sync** (`->` and `->>` are the same call).

A left-pointing head reverses the message (`Foo <- Bar` ≡ `Bar -> Foo`);
heads at both ends make it **bidirectional** (rendered double-headed, no
activation effect).

Other statements:

| Line | Meaning |
| --- | --- |
| `note over a[, b]: text` | note spanning one or two participants |
| `note left of a: text` / `note right of a: text` | note beside a lifeline |
| `alt <label>` / `else <label>` / `end` | alternative frames; davidje13's `if <cond>` / `else if <cond>` / `else` parse as the same frame (each `else if` is one more labeled else-branch) |
| `opt <label>` / `end` | optional frame |
| `loop <label>` / `end` | loop frame; `repeat <label>` is an alias |
| `group <label>` / `end` | plain labeled frame around a run of messages — annotation only, no alt/opt/loop semantics. (Not Mermaid's `box`: that is *horizontal* participant grouping, which stays reserved — the viewer renders no participant grouping; containment shows as muted parent context in headers and Info.) Frames of every kind nest |
| `divider: label` / `divider <type>: label` | full-width divider row ("3 days later"); `<type>` ∈ `line` (default rule) / `space` (blank gap) / `delay` (time gap) / `tear` (torn-edge elision) picks the rendering |
| `… [i-0031]` | optional trailing interface link on any message — ties it to a modelled Interface id (error if unknown) |
| `attach <path>` | links a sample payload file to the **most recent message** in the current scenario (added 2026-08-30; schema.md "Attachments" owns the path rules — grammar, model-dir resolution, UTF-8, formats). The whole rest of the line is the path. Frames and notes don't reset recency; `attach` with no preceding message in the scenario is a `parse_error`. Multiple `attach` lines stack in authored order |
| `%% comment` / `# comment` | comment line |

**Multiline text:** every label and note is one physical line in the doc;
`\n` (davidje13 form) and `<br/>` (Mermaid form) inside it produce line
breaks in the rendered text. Inline markdown formatting in labels is
deferred — text renders plain.

- A bare name used in a message without declaration resolves as an entity/
  user id (case-insensitive per the id rules); if it resolves nowhere it
  becomes an ad-hoc participant **with a warning** — typos surface, ad-hoc
  use stays cheap. Entity ids, interface ids, and self-defined names
  coexist in one flow by design.
- **Activation:** by default a sync call activates its target until the
  matching reply (auto-activation). A scenario containing any explicit
  `+`/`-` marker switches to **manual** activation for that whole scenario
  — the two schemes never mix. Auto pairing (2026-08-25): in flattened
  document order, a reply from B to A closes the most recent open sync
  call A→B (LIFO per direction pair); unmatched replies are silent.
  Marker placement: after direction normalization `+` is legal only on
  the receiving endpoint and `-` only on the sending endpoint; wrong-end
  or bidirectional markers are parse errors. A `-` whose bar is not open
  still compiles, with a warning — the renderer clamps.
- **Reserved keywords** we deliberately do not support fail with a named
  parser error (never silently parse as a message): `par`, `critical`,
  `break`, `box` (participant grouping is not rendered — containment
  shows as header context only),
  `autonumber` (playback numbers steps), `activate` / `deactivate`
  statement forms (the `+`/`-` markers cover it), `create`, `destroy`,
  `rect`, `link`/`links`, davidje13's `note between`, `state over`,
  `text left`/`text right`, and `divider … with height N` (deterministic
  layout owns spacing — no per-doc pixel knobs).

## Compilation (Python)

Per index.md principle 5: Python validates and compiles; the app projects
and renders. `_arch/v3/sequence.py` parses flow docs and reports findings
through the standard validation contract with file/line/column locations.
`arch.validate` and the CLI `validate` include discovered flow docs; any
error in any flow doc fails `generate` atomically, exactly like model
errors. Errors additionally cover: reserved keywords (named as deferred),
an unpaired deferred id (`...req` with no send or no completion), a
completion preceding its send or crossing scenarios, and unknown interface
links. Advisory warnings: unresolved bare participant names, a sync call
left open at scenario end while a later same-pair call was closed
(crossed pairing — auto scenarios only, per the pairing rule above),
docs above 30 participants or scenarios above 300 items, and sequence
intervals referencing milestones on no timeline (the dangling case after
`advance` — `advance` does **not** rewrite flow docs; the warning routes
the manual fix).

Finding codes (2026-08-25, pinned by the parser vectors) — reused from
model validation: `missing_required`, `duplicate_id`,
`unresolved_milestone`, `invalid_interval`. New errors:
`reserved_keyword`, `parse_error`, `invalid_id`, `unresolved_participant`,
`unresolved_interface`, `unpaired_defer`, and the attachment codes shared
with model validation (`invalid_path`, `unresolved_file`, `invalid_file` —
schema.md "Attachments", anchored at the `attach` line). New warnings:
`implicit_participant`, `dangling_interval`, `crossed_reply`,
`unmatched_activation`, `large_scenario`, `large_attachment`. An errored line is skipped
(opens nothing, pairs with nothing); an unclosed frame anchors its error
at the opening line; frontmatter findings anchor at the offending key's
line (line 1 for a missing key). Docs are processed in sorted filename
order (a cross-doc duplicate flow id errors on the later file) and the
compiled `sequences` array is sorted by flow id.

The payload gains a top-level `sequences` key (after the entity
collections), compiled deterministically:

```jsonc
"sequences": [
  { "id": "order-checkout", "name": "…", "description": "…", "tags": [],
    "intervals": [ … ],            // per timeline, same shape as entity rows
    "participants": [
      { "id": "customer", "ref": "users:customer" },      // model-backed
      { "id": "psp", "label": "External PSP" }            // ad-hoc
    ],
    "scenarios": [
      { "id": "happy-path", "name": "Happy path", "description": "…",
        "items": [                  // document order; frames nest
          { "kind": "sync", "from": "customer", "to": "payments-api",
            "text": "Place order", "interface": "i-0031" },
          { "kind": "lost", "from": "payments-api", "to": "psp", "text": "…" },
          { "kind": "sync", "to": "payments-api", "external": "in", "text": "…" },
          { "kind": "async", "from": "payments-api", "defer": "req", "text": "…" },
          { "kind": "async", "defer": "req", "to": "psp" },   // completion
          { "divider": "3 days later", "style": "delay" },
          { "frame": "alt", "label": "Soft decline", "items": [ … ],
            "else": [ { "label": "Hard decline", "items": [ … ] } ] },
          { "note": "…", "placement": "over", "at": ["psp"] }
        ] } ] }
]
```

Message `kind` is `sync` / `reply` / `async` / `lost` (the compiler
normalizes reversed arrows, so `from`/`to` always follow message
direction); `"bidi": true` marks double-headed arrows; `"wavy": true`
preserves a `~` line for rendering; explicit activation markers compile to
`"activate": true` (on the receiver) / `"deactivate": true` (on the
sender), and the scenario carries `"activation": "auto" | "manual"`.
External messages omit the outside endpoint and carry
`external: "in" | "out"` plus `"edge": "right"` when the `]` edge is used
(left is the default and dropped); a deferred pair is two items sharing `defer`
(send omits `to`, completion omits `from`), validated as exactly one of
each with the completion later in the same scenario. Frame kinds are
`alt` / `opt` / `loop` / `group` (aliases normalized away — `if` becomes
`alt`, `repeat` becomes `loop`); notes carry `placement: "over" | "left" |
"right"` and `at` (one or two participant ids); divider `style` is
`line` / `space` / `delay` / `tear`. A message with `attach` statements
carries `"attachments": ["files/…", …]` (authored order, omitted when
empty); the referenced files' text embeds once, deduplicated by path, in
the payload's top-level `files` map (report.md payload contract —
shared with interface attachments). Label text reaches the payload with
line breaks already unescaped (`\n` / `<br/>` → newline). Omitted keys
follow the payload contract's drop-defaults rule. Model-backed
participants carry `ref` (`kind:id` node key — the client joins to the
entity row for box content, containment, and liveness) with the canonical
case-normalized model id as participant id; declared ad-hoc participants
carry `label` (plus `actor: true` for `actor` lines); implicit ad-hoc
participants (bare unresolved names) carry id only.

## Renderer decision (2026-08-25)

Requirements that drove it: participant headers must be the **same
entity-box component** as the canvas; the interaction contract below
(playback, hide, focus, sticky headers, search) is state over our own
data model; single-file offline bundle; MIT-class licenses; theming
shared with the app.

Alternatives surveyed (2026-08-25 web re-survey + the 2026-08-11 POC spike
in `plans/arch/react-flow-poc/`, deleted 2026-08-25 — git history):

| Option | License | Verdict |
| --- | --- | --- |
| davidje13/SequenceDiagram | LGPL-3.0 | rejected — license alone kills it in a single-file bundle; black-box SVG, no coordinate API |
| Mermaid (sequence) | MIT | rejected — multi-MB bundle (poor tree-shaking), black-box SVG, no rendering hooks; every interaction fights render-from-text |
| ZenUML `@zenuml/core` | MIT | rejected — bundles its own React 19 + Tailwind (second React root); POC measured an 869 KB gzip chunk, fragile label-class semantic hooks, no stable ids, no public layout API |
| js-sequence-diagrams | BSD-2 | rejected — dead project; WebFontLoader fetches remote fonts (violates the zero-network gate) |
| layout-as-data engines | — | none exist for sequence diagrams |
| **custom layout + React rendering** | — | **adopted** |

Adopted: sequence layout is the one diagram type that needs no layout
engine — lifeline x = participant column order × uniform column width,
message y = row index × row height, activation bars = interval stacks,
frames = nesting depth. `seqlayout.ts` is a pure deterministic function
from (compiled scenario, view state: hidden set, focus) to column/row
assignments and elision runs. Rendering is React DOM for the
participant header row — **literally the canvas entity-box component** for
model-backed participants (context line, icon, description, badges; the
READ-depth anatomy), a neutral dashed variant for ad-hoc participants — and
one plain SVG layer underneath for lifelines, activation bars, arrows,
frames, and notes. No React Flow, no elkjs, no new dependency. The POC's
native `SequenceCanvas.tsx` is the donor pattern for stepping/selection
state; its ZenUML half is dead.

## Interaction contract (v1)

Normative for the executor chunk. Revised 2026-08-27 to the confirmed
direction ([ui-polish-direction.md](ui-polish-direction.md) "Sequence
diagrams" + "App shell") — sequence controls live in the **View** dock,
never in floating panels or the header. Reuses shared machinery wherever
one exists: graduated dimming tiers, the Info and Data docks, the
lower-left Map control, arrowhead/label styling, reduced-motion and
non-color-cue rules.

- **SEQ-VIEW** — sequences are entries in View's grouped diagram list
  under **Sequences** (one per authored flow doc); with zero sequences in
  the payload the group does not exist (progressive disclosure, same rule
  as the Stage control). Opening one makes that sequence the active
  diagram; View then shows the sequence controls: Scenario, compact
  playback, local search, and the participant list.
- **SEQ-SCEN** — **Scenario is a dropdown** of the doc's scenarios; with
  one scenario its name shows without an active control. The scenario
  prose renders as a collapsible description line. Switching preserves
  participant focus and visibility where the same participants remain.
- **SEQ-PLAY** — the compact playback row in View holds Previous,
  Play/Pause, Next, and the current step count; First, Last, and speed
  live in an overflow menu or keyboard shortcuts. The current message and
  its two participants render at full emphasis; everything else follows
  the selection dimming tiers. The diagram scrolls to keep the current
  message visible; play advances on a fixed cadence (tune by eye at the
  gate); `prefers-reduced-motion` jumps without animated scrolling.
- **SEQ-SEARCH** — local sequence search lives in View (`Cmd/Ctrl+F`):
  matches message text, participant names/ids, and linked interface
  ids/names; shows "n of m" with prev/next cycling; matches get the
  emphasis treatment and ticks in the Map overview. Transient — never in
  the fragment. Global search stays `Cmd/Ctrl+K`.
- **SEQ-STICKY** — the participant header row stays pinned (`position:
  sticky`) while the diagram scrolls vertically; horizontal scroll moves
  headers, lifelines, and messages together. Long diagrams never lose the
  column labels.
- **SEQ-PART** — every participant is an individual lifeline. Containment
  renders only as muted parent context in the participant header and in
  Info — there are **no** C4 group bands, collapsed groups, merged
  lifelines, retargeted group messages, or group self-loop aggregation
  (removed 2026-08-27). Ad-hoc participants use the neutral dashed header
  variant.
- **SEQ-FOCUS** — focus mode: focusing a participant compresses every
  message not involving it into a **gap marker** ("12 messages") without
  hiding the focused lifeline; clicking a marker peeks its run inline
  until focus changes.
- **SEQ-HIDE** — hide/show: an explicit eye control on each row of View's
  participant list hides that participant; hidden lifelines leave the
  layout and any message touching one elides into the same gap markers.
  *Deliberate divergence from the canvas dim-only rule:* horizontal space
  is the binding constraint in sequence diagrams, and hiding is an
  explicit per-participant act in View, not a lens semantic — the tag
  lens still only dims.
- **SEQ-MAP** — the shared lower-left **Map** control opens a vertical
  sequence overview (sequence diagrams are tall, not wide): compressed
  message ticks, emphasis marks for the current step and search matches,
  a draggable viewport rectangle, click-to-jump.
- **SEQ-KIND** — message kinds by shape: sync = solid line + filled
  arrowhead; reply = dashed + open head; async = solid + open half-head;
  lost/failed = cross head stopping short of the target; bidirectional =
  heads at both ends; a `~` line renders wavy; external = arrow to/from a
  small stub at the diagram margin (the boundary-stub visual language); a
  deferred pair renders as one diagonal arrow from its send row to its
  completion row — the visible crossing IS the point. Shape carries the
  distinction (never color alone); a small chip row in View names the
  kinds present. Dividers render as full-width labeled rows and act as
  playback narration beats.
- **SEQ-LINK** — selecting a message opens it in **Info** (the same
  adaptive inspector as canvas splines). A message with an interface link
  shows the interface there with a "show on canvas" action that switches
  to Canvas with that interface selected; selecting a model-backed
  participant shows its entity details in Info. Linked request/response
  payload files list under Info's Attachments and open read-only in
  **Data**'s Payload tab (report.md / direction "Data dock") — the same
  attachment flow as architecture interfaces.
- **SEQ-TIME** — time integration: a sequence with an interval is listed
  and openable only at stage positions where it is live (`liveAt` reuse
  over its `intervals`); model-backed participants not live at the
  current position render with the retired/ghost treatment and say so in
  Info. Messages carry no temporal semantics in v1.

Fragment keys (extends the report.md Views table): `seq` (flow id),
`scenario`, `step` (1-based message index, flattened document order),
`focus`, `hide` (list). The `collapse` key is gone with group collapse
(2026-08-27). Shared keys (`timeline`, `time`) keep their meaning;
canvas-only keys are ignored while a sequence is active. Search, scroll,
and peek state are transient.

## Verification

- **Parser vectors** (authoritative, architect-authored — the D12a control
  mechanism): flow docs + expected compiled `sequences` payload + expected
  findings, in `tests/unit/tools/fixtures/arch/sequence/`. AUTHORED
  2026-08-25 — its README carries the driver contract and pinned
  decisions; vectors are the tie-breaker on any wording gap here.
- **Layout vectors** (vitest, the D12b control mechanism): compiled
  scenario + view state (hidden / focus) → expected column order, row
  assignments, and elision runs — indices, not pixels.
- Acme gains 2–3 architect-authored flow docs (at least one multi-scenario,
  one interval-carrying, one ad-hoc participant) — the living fixture.
- Rule-9 Playwright pass: sticky headers under scroll, playback stepping
  from View, Scenario dropdown switch, hide/focus elision, the Map
  vertical overview, clean console, **zero external requests from
  `file://`**.

## Budgets (provisional — agreed when the D12 prompts are authored)

~500 Python source lines (parser + payload + validation + CLI); ~2,200
TS/TSX (layout, SVG layer, header row, View controls, Map overview,
playback, fragments). No new runtime dependency in either language.

## Donors and licensing

- **Grammar:** the union grammar (Mermaid base, davidje13-derived arrow
  forms and extensions) is **reimplemented from published syntax
  documentation only**. Syntax is a method of operation, not protected
  expression — but no parser, renderer, grammar-definition, or test code
  from either project enters this repo. Mermaid (MIT) would permit
  attributed copying; davidje13/SequenceDiagram is **LGPL-3.0 and must
  never be copied**, only read for ideas.
- **Code donors:** the POC's native `SequenceCanvas.tsx` (our code, lift
  freely). Small geometry fragments (row heights, activation offsets,
  wrapping widths) may be harvested from MIT sources (ZenUML, Mermaid)
  with an attribution comment at the ported site.

## Explicitly deferred

The reserved keywords listed in the DSL section (`par`, `critical`,
`break`, `box`, `autonumber`, `activate`/`deactivate` statement forms,
`create`/`destroy`, `rect`, `link`, `note between`, `state over`,
`text left`/`right`, divider heights), inline markdown formatting in
labels, davidje13's simultaneity markers (they break monotonic
document order, which playback and the `step` fragment key depend on;
deferred delivery covers crossing), message-level intervals, sequence
editing, sequence SVG export (rides the D8 client-side export pattern
later), Excel/tabular carriage of sequences, cross-flow links, and
`advance` rewriting flow-doc frontmatter (validation warns instead).
