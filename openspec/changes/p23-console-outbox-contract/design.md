## Context

`feature/display` (currently at commit `fe4e0bad9fecf6bbf8810125a408ae223ba0be23`, "docs(display): restore
console outbox specs") has a complete, working Console outbox protocol contract: an OpenSpec capability, a
human-readable protocol doc, JSON Schemas, example fixtures, and a Python implementation
(`src/ot/console_outbox.py`, 305 lines) that a live `test_console_protocol_fixtures.py` validates against.

That implementation is not portable in isolation: `src/ot/console_outbox.py` does
`from ot.display.state import allowed_roots` and also type-imports `BoundedPreview`, `MessageMetadata` from
`ot.display.models` — the whole display pack, which does not ship until 3.1. `main` at
`151a52b3` (2026-07-04) has none of `ot.display.*` or `ot.console_outbox`.

Report R6 (`wip/release-v3/release-v3-report-2.md` lines 250–271) sets the scope: port the **contract**
(spec + protocol doc + schemas/fixtures) now so Console App client work can start against a frozen
protocol; do not port the coupled runtime.

`main` and `feature/display` diverged 17 commits (feature/display) vs 11 commits (main) since their merge
base `0528a00ea0ffb2b41708be24c06a4c5b1f3d8886`. This change must produce byte-identical copies of the
contract files so that when `feature/display` is later rebased onto `main`, git sees no conflict on those
paths (the branch's own future changes to `console_outbox.py`/display code are unaffected — only the
already-ported contract files must match).

## Goals / Non-Goals

**Goals:**
- Every file needed for a Console client implementer to build against protocol v1 exists on `main`:
  the spec (`openspec/specs/console-outbox/spec.md`), the protocol doc
  (`docs/reference/console-outbox-protocol.md`, linked from `mkdocs.yml` nav), and the JSON Schemas +
  fixtures (`tests/fixtures/console-protocol/{schemas,fixtures}/`).
- A CI-enforced test proves the fixtures are schema-valid, so the contract cannot silently drift.
- Every ported file is textually identical to its `feature/display` source (verified by `git diff`),
  except: (a) the Purpose annotation added to `console-outbox/spec.md` per report R6's "protocol v1 —
  server implementation ships with display (3.1)" instruction, and (b) the two branch test functions that
  import `ot.console_outbox`/`ot.display.models`, which are dropped because that code does not exist on
  `main`.

**Non-Goals:**
- No HTTP route is registered. No `GET /api/console/outbox` or `POST /api/console/outbox/ack` handler is
  added anywhere in `src/`.
- No `src/ot/console_outbox.py`, no `ot.display.*` package, no `auth/console-outbox.key` provisioning.
- No change to unknown-route 404 behavior — an unauthenticated request to `/api/console/outbox` on `main`
  after this change 404s exactly as any other undefined path does today (verified, not just assumed — see
  Verification in `tasks.md`).
- No new runtime dependency. `jsonschema` is already resolvable (transitive dependency of `mcp`, see
  `uv.lock`); it is not added to `pyproject.toml`.

## Decisions

**1. Full verbatim port, not a summary.** All five schema files and all eight fixture files from
`feature/display:tests/fixtures/console-protocol/` are ported unchanged (byte-for-byte). A partial or
"representative" subset would break the "contract text identical" rebase-cleanly acceptance check in
report R6 and would leave the Console client team without fixtures for the modes they need
(`file_ref`, `file_diff_ref`).

Source paths (all on `feature/display`, verified via `git ls-tree -r feature/display --name-only`):
- `openspec/specs/console-outbox/spec.md`
- `docs/reference/console-outbox-protocol.md`
- `tests/fixtures/console-protocol/schemas/event-envelope.schema.json`
- `tests/fixtures/console-protocol/schemas/instance-snapshot.schema.json`
- `tests/fixtures/console-protocol/schemas/display-message.schema.json`
- `tests/fixtures/console-protocol/schemas/outbox-batch.schema.json`
- `tests/fixtures/console-protocol/schemas/outbox-ack.schema.json`
- `tests/fixtures/console-protocol/fixtures/display-message-event.json`
- `tests/fixtures/console-protocol/fixtures/empty-outbox-batch.json`
- `tests/fixtures/console-protocol/fixtures/file-diff-ref-display-message.json`
- `tests/fixtures/console-protocol/fixtures/file-ref-display-message.json`
- `tests/fixtures/console-protocol/fixtures/inline-display-message.json`
- `tests/fixtures/console-protocol/fixtures/instance-snapshot.json`
- `tests/fixtures/console-protocol/fixtures/outbox-ack.json`
- `tests/fixtures/console-protocol/fixtures/outbox-batch.json`
- `tests/unit/core/test_console_protocol_fixtures.py` (ported in **trimmed** form — see Decision 3)

**2. `outbox-batch.schema.json` uses an unresolvable relative `$ref`.** Its `events` property is
`{"$ref": "event-envelope.schema.json"}` — a bare relative filename, not a URI resolvable by a default
`jsonschema.RefResolver`/registry (the schema's own `$id` is `https://onetool.beycom.online/schemas/...`,
so a plain `Draft202012Validator(...).validate(...)` call would raise `RefResolutionError` trying to fetch
that filename over HTTP). The branch's test worked around this by inlining the resolved sub-schema before
validating (see its `_schema()` helper: when loading `outbox-batch.schema.json`, it substitutes
`schema["properties"]["events"]["items"]` with the loaded `event-envelope.schema.json` content). Port that
same helper verbatim — do not "fix" the `$ref` in the vendored schema file itself, since the schema file
must stay byte-identical to `feature/display` for the rebase-cleanly check.

**3. Drop the two branch tests that require unported runtime code.** The branch's
`test_console_protocol_fixtures.py` has three test functions:
- `test_vendored_console_fixtures_validate_against_schemas` — pure fixture/schema validation, no
  `ot.console_outbox` import. **Port this one.**
- `test_current_mcp_display_payload_validates_against_console_schema` — imports
  `ot.console_outbox.build_display_payload` and `ot.display.models.*`. **Do not port**: that code does not
  exist on `main` and this change explicitly does not add it.
- `test_current_mcp_instance_snapshot_validates_against_console_schema` — imports
  `ot.console_outbox.build_instance_snapshot`. **Do not port**, same reason.

Porting only the first function, unmodified apart from dropping the other two and their now-unused
imports (`ot.console_outbox`, `ot.display.models`, `datetime`/`UTC` if no longer referenced), satisfies
report R6's "fixtures validate against the schemas in CI" acceptance check without introducing any
`ot.display`/`ot.console_outbox` import on `main`.

**4. Purpose-section handling for the new capability.** `openspec archive` auto-generates a placeholder
Purpose ("TBD - created by archiving change ...") for any brand-new capability spec folder
(`@fission-ai/openspec` `buildSpecSkeleton`, confirmed by reading
`dist/core/specs-apply.js`). The delta spec in this change (`specs/console-outbox/spec.md`) therefore
carries the exact target Purpose text in a reference block above `## ADDED Requirements`, and `tasks.md`
has an explicit post-sync task to paste it into `openspec/specs/console-outbox/spec.md` — otherwise the
archived spec would ship with a "TBD" Purpose forever.

**5. `mkdocs.yml` nav entry.** `feature/display`'s `mkdocs.yml` has `- Console Outbox Protocol:
reference/console-outbox-protocol.md` under `nav: > Reference:`, positioned between the `CLIs` block and
the `Tools` block. `main`'s `mkdocs.yml` Reference block (lines 154–192) does not have this entry yet
(confirmed via `git diff main feature/display -- mkdocs.yml`, plus grep on main). Add the identical single
line in the identical position so the protocol doc is reachable from the built docs site, not just present
in the file tree.

## Risks / Trade-offs

- **[Risk] A future 3.1 display-pack change accidentally re-derives a slightly different contract**
  (e.g. renumbering `protocol_version`, changing a payload mode name) → **Mitigation**: this change's spec
  requirement "Console Outbox Protocol Fixtures Stay Schema-Valid" plus the CI test gives 3.1 a concrete,
  enforced baseline to diff against; any drift shows up as either a failing rebase or a failing fixture
  test.
- **[Risk] Implementer "fixes" the unresolvable `$ref` in `outbox-batch.schema.json` directly** (e.g. by
  editing `$id`/`$ref` to be self-consistent) → this would make the ported schema byte-different from
  `feature/display`, breaking the "contract text identical" verification → **Mitigation**: Decision 2 above
  states explicitly not to touch the schema; solve the `$ref` resolution problem only in the test helper,
  exactly as the branch does.
- **[Risk] Someone adds a stub `/api/console/outbox` route "for completeness"** → violates report R6's
  "do not add endpoints that 404 differently than any other unknown route" → **Mitigation**: explicit
  non-goal above, plus a `tasks.md` verification step that curls the path and confirms it 404s the same as
  an arbitrary unknown path.

## Implementation guardrails

- **No compatibility shims or partial ports.** Every file listed in Decision 1 is ported in full. There is
  no "abbreviated" version of any schema or fixture. If a file cannot be ported verbatim for a concrete
  technical reason, stop and report — do not silently drop content.
- **No stubbing or TODO-deferral.** If the fixture-validation test cannot pass as specified (e.g. the
  `$ref` workaround in Decision 2 does not work against the installed `jsonschema` version), stop and
  report the exact failure — do not weaken the test (e.g. by skipping validation of the `outbox-batch`
  cases) to make it pass.
- **Tests are mandatory, not optional.** The fixture-validation test (task group 3) is part of this
  change's completion criteria, not a follow-up. `just check` must pass before the change is considered
  done.
- **Every `rg`/verification command in `tasks.md` Verification section must actually be run, and must
  produce the stated result.** In particular `rg -n "console_outbox" src/` must return empty — if it does
  not, the change is not done; do not report success anyway.
- **Do not touch `src/ot/display/` or any display-pack code.** That dead-code deletion is owned by
  `p22-technical-foundation`, not this change. If you notice `src/ot/display/` exists on `main` while
  implementing this change, leave it alone and do not reference it from anything you add.
