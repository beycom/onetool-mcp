# Sequence parser vectors (D12a spec)

Authoritative fixtures for the sequence flow-doc parser/compiler — the
control mechanism for D12a, consumed by the Python unit suite. They are
READ-ONLY for executors: a vector that looks wrong is a stop-and-ask,
never an edit. Owner doc: `plans/arch/arch-v3/sequence.md` (DSL,
compilation, payload shape); this README pins the driver contract and the
decisions the vectors encode.

| File | What |
| --- | --- |
| `model.yaml` | Minimal schema-v3 model the flows resolve against: one system, two containers, a component, a code row, a user, interface `i-0001`, timeline `program` = [m1, m2], plus `m-orphan` (declared on no timeline — the dangling-interval case). Its three `unused_milestone` model warnings are expected: milestones are referenced only by flow docs. |
| `flows/*.md` | One vector doc per concern (see table below). Each parses independently against `model.yaml`. |
| `crossdoc/*.md` | Two docs sharing a flow id — the cross-doc `duplicate_id` case (docs process in sorted filename order; the later file carries the error, anchored at its `id:` line). |
| `files/*` | Sample attachment files beside `model.yaml` (added 2026-08-30): two JSON, one CSV, and `binary.bin` (deliberately invalid UTF-8 — the `invalid_file` case). Referenced by the `attachments*` vectors via `attach`. |
| `expected.json` | Per-doc expected findings + compiled `sequences` entry. |

| Flow doc | Covers |
| --- | --- |
| `order-checkout.md` | Showcase, zero findings: frontmatter (description, tags, `start_in`), doc-level declared participants (model-backed, ad-hoc `as`, `actor`, one unused), two scenarios with prose, interface links, alt/else, delay divider, note over two, `%%` and `#` comments. |
| `arrows.md` | The compositional arrow matrix: every head/line combination and its kind, reversal (`<-` forms), bidi, wavy, self-message, unlabeled message, label-less interface link, case-insensitive id resolution (`Pay-API`), refs into all five participant collections, implicit scenario `main`. |
| `activation.md` | Auto vs manual scenarios in one doc; `+`/`-` markers compile to `activate`/`deactivate`; `activation` key omitted when auto; bounded interval (`end_in: m1` → live `[[0, 1]]`). |
| `frames.md` | Frame nesting; `if`/`else if`/`else` → `alt` and `repeat` → `loop` alias normalization; label-less `else` branch; `group`; all divider styles incl. defaulted `line`; all note placements; `\n` and `<br/>` unescaping in notes and message labels. |
| `deferred-external.md` | External edge endpoints `[`/`]` both directions (right edge carries `"edge": "right"`), reversed external, a valid deferred pair split across the scenario. |
| `warnings.md` | All four vector-pinned warnings: `dangling_interval` (interval never live → `"live": []`), `implicit_participant` (bare unresolved name; compiles id-only), `crossed_reply`, `unmatched_activation`. Doc still compiles. |
| `errors.md` | All 15 reserved keywords (one error each, line skipped), unknown interface, declared-unresolved participant, headless arrow, `x` with a left head, activation markers on the wrong end, both `unpaired_defer` shapes, bare `end`, unclosed frame (anchored at its opening line), invalid heading slug, duplicate scenario slug. Compiles to nothing (`sequence: null`). |
| `frontmatter-bad.md` | Missing required frontmatter key (anchored line 1), unresolved interval milestone. |
| `attachments.md` | Zero findings (added 2026-08-30, P21 re-scope): `attach` statements — two files stacking on one message, attach to a reply inside a frame, the same path attached twice in one doc (per-message lists keep authored order; payload-level dedup is the `files` map's job, tested by a P21-listed unit test, not here). Resolves against `files/` beside `model.yaml`. |
| `attachments-bad.md` | Every `attach` error (added 2026-08-30): attach before any message in the scenario (`parse_error`), missing file (`unresolved_file`), `..` escape and whitespace in path (`invalid_path` ×2), non-UTF-8 file (`invalid_file`, `files/binary.bin`). Compiles to nothing (`sequence: null`). |

## Driver contract

For each `flows/*.md`: parse + compile the doc against `model.yaml`; compare

- **findings** as `(severity, code, line)` triples, both sides sorted by
  `(line, code)`. `line` is the physical 1-based line in the `.md` file
  (frontmatter included). Columns are deliberately unpinned (must be ≥ 1);
  message text is unpinned but must name the offending token.
- **sequence** by deep JSON equality against the compiled payload entry
  (`null` = the doc has errors and compiles to nothing).

For `crossdoc/`: compile the directory as one set; expect exactly the
listed findings. A doc-set with any error fails `generate` atomically.

## Decisions pinned by these vectors

(folded into sequence.md the same day; vectors are the tie-breaker)

- **Finding codes** — reused from model validation: `missing_required`,
  `duplicate_id`, `unresolved_milestone`, `invalid_interval`. New errors:
  `reserved_keyword`, `parse_error`, `invalid_id`,
  `unresolved_participant`, `unresolved_interface`, `unpaired_defer`. New
  warnings: `implicit_participant`, `dangling_interval`, `crossed_reply`,
  `unmatched_activation`, `large_scenario`.
- **`large_scenario`** thresholds: > 30 participants per doc or > 300
  items per scenario — pinned here, tested by a D12a-listed unit test,
  not a vector (a 300-line fixture doc earns nothing).
- **Auto-activation pairing** (feeds `crossed_reply` and D12b bars): in
  flattened document order, a reply from B to A closes the most recent
  open sync call A→B (LIFO per direction pair). `crossed_reply` fires on
  a sync call left open at scenario end while a *later* same-pair call
  was closed; auto scenarios only. Unmatched replies are silent.
- **Activation markers**: after direction normalization, `+` is legal
  only on the receiving endpoint, `-` only on the sending endpoint;
  wrong-end or bidirectional markers are `parse_error`. A `-` whose bar
  is not open still compiles (`deactivate: true`) with an
  `unmatched_activation` warning; the renderer clamps.
- **Arrow edge rules**: at least one head is required (headless lines are
  `parse_error`); an `x` head with a left head is `parse_error` (lost
  messages are directional). Bidi `from` = the left-hand endpoint as
  written.
- **Compiled participants**: model-backed rows use the canonical model id
  (case-normalized) as participant id and carry `ref`; declared ad-hoc
  carry `label` (+ `actor: true`); implicit ad-hoc (bare unresolved name)
  carry id only. Order: declaration order, then first appearance,
  including declared-but-unused participants.
- **Drop-defaults** (payload-contract rule applied here): omitted
  `text`, `description`, empty `tags`, `activation` when `auto`, divider
  `style` when `line`, `edge` when left. Note `placement` is always
  present. `intervals` always present, entity-row segment shape
  (`live` empty when never live; `clips` always `[]` — sequences are
  never clipped).
- **Error recovery**: an errored line is skipped (opens nothing, pairs
  with nothing); an unclosed frame anchors its error at the opening
  line; frontmatter findings anchor at the offending key's line, or
  line 1 for a missing key; duplicate scenario slugs anchor at the later
  heading.
- **`attach` statements** (added 2026-08-30 with the attachments design;
  schema.md "Attachments" owns the path rules): the whole rest of the
  line after `attach ` is the path — grammar `[A-Za-z0-9._/-]+`, no
  leading `/`, no `..` or empty segments (`invalid_path`); resolved
  against the model YAML's directory (`unresolved_file` when missing,
  `invalid_file` when not UTF-8 text). Binds to the **most recent
  message item in the current scenario** in document order (frames and
  notes don't reset recency); `attach` with no preceding message is
  `parse_error`, line skipped. Multiple attaches stack in authored
  order onto the message's `attachments` list (omitted when empty —
  drop-defaults); duplicates within a doc are legal. The
  `large_attachment` warning threshold (> 256 KB) is pinned by a
  P21-listed unit test, not a vector.

Provenance (2026-08-25): architect-authored. `expected.json` is assembled
by scratch tooling (not kept) that hand-carries the compiled objects and
looks finding line numbers up by content, so anchors are exact.
Interval segments follow the payload contract's `_live_segments`
convention (end `null` when the row is live through the final position).
