## Why

The separate OneTool Console App needs a frozen, versioned protocol contract to build against before the
Console display feature ships. The full contract — spec, protocol doc, and JSON schemas/fixtures — already
exists on the `feature/display` branch (commit `fe4e0bad`, "docs(display): restore console outbox specs"),
but the server implementation that satisfies it (`src/ot/console_outbox.py`) imports
`ot.display.state.allowed_roots` and other display-pack internals that are not shipping in V3. Porting the
contract now (docs + schema fixtures only) lets Console client work start immediately without pulling the
coupled, unfinished display runtime onto `main`. The runtime endpoints ship with display in 3.1.

## What Changes

- Add a new `console-outbox` OpenSpec capability on `main`, ported verbatim from
  `feature/display:openspec/specs/console-outbox/spec.md`, describing the polling/ack protocol, the
  separate outbox consumer key, at-least-once bounded-FIFO retention, and the `instance.snapshot` /
  `display.message.created` event envelopes with `inline` / `file_ref` / `file_diff_ref` payload modes.
  The spec's Purpose section is annotated "protocol v1 — server implementation ships with display (3.1)".
- Add `docs/reference/console-outbox-protocol.md`, ported verbatim from
  `feature/display:docs/reference/console-outbox-protocol.md`, and register it in `mkdocs.yml` nav under
  **Reference** (matching the branch's nav placement, between CLIs and Tools).
- Add the protocol JSON schemas and fixtures under `tests/fixtures/console-protocol/{schemas,fixtures}/`,
  ported verbatim from the same paths on `feature/display`.
- Add a fixture-validation unit test (`tests/unit/core/test_console_protocol_fixtures.py`, a trimmed port
  of the branch's test) that validates every vendored fixture against its JSON Schema in CI. The two
  branch test functions that import `ot.console_outbox` / `ot.display.models` are **not** ported (that
  runtime code does not exist on `main`).
- **No runtime code**: `src/ot/console_outbox.py`, the `/api/console/outbox` and `/api/console/outbox/ack`
  HTTP endpoints, and all `ot.display.*` code stay off `main`. No new route is registered anywhere; unknown
  paths continue to 404 exactly as they do today (no Console-specific 404 behavior is introduced).

## Capabilities

### New Capabilities

- `console-outbox`: Documents (contract-only, no server implementation on `main`) the versioned Console
  outbox protocol — polling and acknowledgement semantics, the separate outbox consumer key and its
  authorization boundary, at-least-once bounded-FIFO retention, and the stable event/payload envelope
  shapes that the Console App and the future (3.1) display-pack server implementation must both honor.

### Modified Capabilities

(none — this change only adds new files; no existing capability's requirements change)

## Impact

- **Affected code**: none at runtime. Additions only: `openspec/specs/console-outbox/spec.md`,
  `docs/reference/console-outbox-protocol.md`, `mkdocs.yml` (nav entry),
  `tests/fixtures/console-protocol/schemas/*.json`, `tests/fixtures/console-protocol/fixtures/*.json`,
  `tests/unit/core/test_console_protocol_fixtures.py`.
- **Dependencies**: none new. `jsonschema` (used by the fixture-validation test) is already resolvable in
  the environment as a transitive dependency of `mcp` (see `uv.lock`); it does not need to be added to
  `pyproject.toml`.
- **Downstream dependency**: `p22-technical-foundation` deletes the orphaned `src/ot/display/` dead code
  (R8 M3) — that deletion is owned by p22, not this change. This change never adds `ot.display.*` or
  `ot.console_outbox` code, so there is no ordering conflict either way.
- **Future work (not this change)**: the 3.1 display release will add `src/ot/console_outbox.py`, the two
  live HTTP endpoints, `auth/console-outbox.key` provisioning, and the `ot.display.*` runtime that the
  branch's full test suite (`test_current_mcp_display_payload_validates_against_console_schema`,
  `test_current_mcp_instance_snapshot_validates_against_console_schema`) exercises. Those two tests and
  their `ot.console_outbox` / `ot.display.models` imports are explicitly out of scope here.
