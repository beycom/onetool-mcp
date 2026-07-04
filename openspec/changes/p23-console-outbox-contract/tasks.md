## 1. Port the OpenSpec capability spec

- [x] 1.1 Confirm `feature/display` still has the source content at
      `feature/display:openspec/specs/console-outbox/spec.md` via
      `git show feature/display:openspec/specs/console-outbox/spec.md`. If the branch has moved and the
      content differs from the quoted text in `specs/console-outbox/spec.md` of this change, stop and
      report the drift — do not silently reconcile it.
- [x] 1.2 Run `openspec archive` (or the project's `opsx:sync`/`opsx:apply` flow) to apply this change's
      `specs/console-outbox/spec.md` delta (`## ADDED Requirements`) to a new
      `openspec/specs/console-outbox/spec.md` on `main`.

## 2. Fix the auto-generated Purpose placeholder

- [x] 2.1 After sync/archive, `openspec/specs/console-outbox/spec.md` will have a Purpose section reading
      `TBD - created by archiving change p23-console-outbox-contract. Update Purpose after archive.`
      (this is expected — the OpenSpec archive tool always auto-generates this placeholder for brand-new
      capabilities; it is not an error).
- [x] 2.2 Replace that placeholder Purpose section with:

      ```
      Defines the signed MCP-owned Console outbox protocol used by the separate OneTool Console App to
      consume read-only MCP instance and display events.

      **Status: protocol v1 — server implementation ships with display (3.1).** This capability defines
      the wire contract only. No `main` code implements these endpoints yet; `src/ot/console_outbox.py`
      and the `/api/console/outbox` / `/api/console/outbox/ack` HTTP routes ship with the display pack in
      release 3.1.
      ```
- [x] 2.3 Confirm the resulting `openspec/specs/console-outbox/spec.md` Requirements section (everything
      below `## Requirements`) is textually identical to `feature/display:openspec/specs/console-outbox/spec.md`
      (diff the Requirements bodies; the only intentional difference anywhere in the file is the Purpose
      section from 2.2).

## 3. Port the protocol doc

- [x] 3.1 Copy `feature/display:docs/reference/console-outbox-protocol.md` to
      `docs/reference/console-outbox-protocol.md` on `main`, unchanged (54 lines on the branch — verify
      the copy is line-for-line identical with `git show feature/display:docs/reference/console-outbox-protocol.md | diff - docs/reference/console-outbox-protocol.md`, expect no output).
- [x] 3.2 Add the nav entry to `mkdocs.yml` under the `Reference:` block, between the `CLIs:` sub-block
      and the `Tools:` sub-block (matching `feature/display`'s `mkdocs.yml` line 161 placement):

      ```yaml
      - Console Outbox Protocol: reference/console-outbox-protocol.md
      ```

## 4. Port the JSON Schemas

- [x] 4.1 Create `tests/fixtures/console-protocol/schemas/event-envelope.schema.json` — copy verbatim from
      `feature/display:tests/fixtures/console-protocol/schemas/event-envelope.schema.json`.
- [x] 4.2 Create `tests/fixtures/console-protocol/schemas/instance-snapshot.schema.json` — copy verbatim
      from `feature/display:tests/fixtures/console-protocol/schemas/instance-snapshot.schema.json`.
- [x] 4.3 Create `tests/fixtures/console-protocol/schemas/display-message.schema.json` — copy verbatim from
      `feature/display:tests/fixtures/console-protocol/schemas/display-message.schema.json`.
- [x] 4.4 Create `tests/fixtures/console-protocol/schemas/outbox-batch.schema.json` — copy verbatim from
      `feature/display:tests/fixtures/console-protocol/schemas/outbox-batch.schema.json`. Do **not**
      "fix" its `events` property's `{"$ref": "event-envelope.schema.json"}` — it is intentionally
      resolved by the test helper in task 6.2, not by editing the schema (see `design.md` Decision 2).
- [x] 4.5 Create `tests/fixtures/console-protocol/schemas/outbox-ack.schema.json` — copy verbatim from
      `feature/display:tests/fixtures/console-protocol/schemas/outbox-ack.schema.json`.
- [x] 4.6 Verify all five schema files are byte-identical to their branch sources:
      `for f in event-envelope instance-snapshot display-message outbox-batch outbox-ack; do git show feature/display:tests/fixtures/console-protocol/schemas/$f.schema.json | diff - tests/fixtures/console-protocol/schemas/$f.schema.json; done` — expect no diff output for any of the five.

## 5. Port the fixtures

- [x] 5.1 Create `tests/fixtures/console-protocol/fixtures/display-message-event.json` — copy verbatim
      from `feature/display:tests/fixtures/console-protocol/fixtures/display-message-event.json`.
- [x] 5.2 Create `tests/fixtures/console-protocol/fixtures/empty-outbox-batch.json` — copy verbatim from
      `feature/display:tests/fixtures/console-protocol/fixtures/empty-outbox-batch.json`.
- [x] 5.3 Create `tests/fixtures/console-protocol/fixtures/file-diff-ref-display-message.json` — copy
      verbatim from `feature/display:tests/fixtures/console-protocol/fixtures/file-diff-ref-display-message.json`.
- [x] 5.4 Create `tests/fixtures/console-protocol/fixtures/file-ref-display-message.json` — copy verbatim
      from `feature/display:tests/fixtures/console-protocol/fixtures/file-ref-display-message.json`.
- [x] 5.5 Create `tests/fixtures/console-protocol/fixtures/inline-display-message.json` — copy verbatim
      from `feature/display:tests/fixtures/console-protocol/fixtures/inline-display-message.json`.
- [x] 5.6 Create `tests/fixtures/console-protocol/fixtures/instance-snapshot.json` — copy verbatim from
      `feature/display:tests/fixtures/console-protocol/fixtures/instance-snapshot.json`.
- [x] 5.7 Create `tests/fixtures/console-protocol/fixtures/outbox-ack.json` — copy verbatim from
      `feature/display:tests/fixtures/console-protocol/fixtures/outbox-ack.json`.
- [x] 5.8 Create `tests/fixtures/console-protocol/fixtures/outbox-batch.json` — copy verbatim from
      `feature/display:tests/fixtures/console-protocol/fixtures/outbox-batch.json`.
- [x] 5.9 Verify all eight fixture files are byte-identical to their branch sources:
      `for f in display-message-event empty-outbox-batch file-diff-ref-display-message file-ref-display-message inline-display-message instance-snapshot outbox-ack outbox-batch; do git show feature/display:tests/fixtures/console-protocol/fixtures/$f.json | diff - tests/fixtures/console-protocol/fixtures/$f.json; done` — expect no diff output for any of the eight.

## 6. Add the fixture-validation test (trimmed port, no runtime imports)

- [x] 6.1 Create `tests/unit/core/test_console_protocol_fixtures.py` containing **only** the
      `test_vendored_console_fixtures_validate_against_schemas` test from
      `feature/display:tests/unit/core/test_console_protocol_fixtures.py`, marked
      `@pytest.mark.unit` and `@pytest.mark.core` (matching the branch). Do **not** port
      `test_current_mcp_display_payload_validates_against_console_schema` or
      `test_current_mcp_instance_snapshot_validates_against_console_schema` — both import
      `ot.console_outbox` / `ot.display.models`, which do not exist on `main` (see `design.md` Decision 3).
      Drop now-unused imports (`ot.console_outbox`, `ot.display.models`, and `datetime`/`UTC` if nothing
      else in the trimmed file references them).
- [x] 6.2 Keep the branch's `_schema()` helper that inlines `event-envelope.schema.json` into
      `outbox-batch.schema.json`'s `events.items` before validation (needed because the vendored
      `$ref` is a bare relative filename `jsonschema` cannot resolve on its own — see `design.md`
      Decision 2). `FIXTURE_ROOT` should point at `tests/fixtures/console-protocol` (relative path used by
      the branch test, run from repo root).
- [x] 6.3 Confirm `jsonschema` imports successfully without any `pyproject.toml`/`uv.lock` change:
      `uv run python -c "import jsonschema; print(jsonschema.__version__)"`.
- [x] 6.4 Run the new test in isolation: `uv run pytest tests/unit/core/test_console_protocol_fixtures.py -v` — all cases in the (single) test function's fixture/schema pairs must pass.

## Verification

- [x] V.1 `test -f openspec/specs/console-outbox/spec.md` succeeds and the file's Requirements section
      matches `feature/display:openspec/specs/console-outbox/spec.md` (task 2.3).
- [x] V.2 `test -f docs/reference/console-outbox-protocol.md` succeeds and
      `git show feature/display:docs/reference/console-outbox-protocol.md | diff - docs/reference/console-outbox-protocol.md`
      produces no output.
- [x] V.3 `grep -n "Console Outbox Protocol: reference/console-outbox-protocol.md" mkdocs.yml` finds the
      nav entry added in task 3.2.
- [x] V.4 All five schema diffs and all eight fixture diffs from tasks 4.6 and 5.9 produce no output.
- [x] V.5 `uv run pytest tests/unit/core/test_console_protocol_fixtures.py -v` passes.
- [x] V.6 `rg -n "console_outbox" src/` returns **empty** (no runtime code was added). This is a hard
      acceptance gate from report R6 — if this command returns any match, the change is not done.
- [x] V.7 `rg -n "ot\.display" src/ --glob '!**/__pycache__/**'` returns **empty** (no display-pack code
      or imports were added by this change — `src/ot/display/` on `main` contains only gitignored
      `.pyc` cache artifacts, zero git-tracked files; this change must not add any tracked file there).
- [x] V.8 Confirm no new HTTP route was registered: `rg -n "api/console/outbox" src/` returns empty (the
      string should only appear in `docs/reference/console-outbox-protocol.md` and
      `openspec/specs/console-outbox/spec.md`, not in `src/`).
      `rg -n "api/console/outbox" docs/ openspec/specs/` should show the doc/spec occurrences.
- [ ] V.9 `feature/display` rebases cleanly over the ported spec: from a scratch worktree,
      `git checkout -b tmp-rebase-check feature/display && git rebase main` for the commits touching
      `openspec/specs/console-outbox/spec.md`, `docs/reference/console-outbox-protocol.md`, and
      `tests/fixtures/console-protocol/**` must produce **no conflicts** on those specific paths (other
      unrelated conflicts, e.g. in `mkdocs.yml` nav ordering around this change's new line, are expected
      and are not a failure of this check — only conflicts on the five path groups above count). Delete
      the temporary branch afterward; do not push or merge it.
- [x] V.10 `just check` (lint + typecheck + test) passes.

## Explicitly out of scope (do not implement here)

- `src/ot/console_outbox.py` and any `ot.display.*` runtime code — ships with display in 3.1.
- `GET /api/console/outbox` / `POST /api/console/outbox/ack` HTTP handlers — ships with display in 3.1.
- `auth/console-outbox.key` provisioning/rotation — ships with display in 3.1.
- Deleting `src/ot/display/` cache artifacts or any dead-code cleanup there — owned by
  `p22-technical-foundation` (R8 M3), not this change.
