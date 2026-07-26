# Assignment feature-ledger-audit

> Final disposition: this assignment inspected the file as an audit lead. The user subsequently
> clarified that it is non-authoritative historical/changelog tracking and MUST NOT become an
> implementation dependency. The proposed feature-ledger validation issue was rejected.

Review revision: `528cac463d21f3b510757e106d31ad310591d56b` with the OpenSpec worktree
change recorded in the run plan.

Goal: enumerate every capability declared in `features/features.yaml`, verify each row against its
named implementation area, and identify code-backed feature classes absent from the ledger.

Owned dimensions: `requirements-specs`, `documentation-dx`.

Owned scope and primary paths: `feature-ledger`; `features/features.yaml`,
`features/feature-tracking.md`, and directly linked specifications/reference indexes.

Read-only dependency context: feature-named runtime modules and
`openspec/changes/pack-guidance-help-and-setup/`.

Explicit exclusions: skill-system findings, generated reference bodies, archived changes, tests,
fixtures, and runtime execution.

Depth and budget: standard static inspection.

Allowed commands: static searches, file reads, and Git metadata only.

Return:

1. A structured feature inventory grouped by platform/core/pack capability, with exact path:line
   evidence.
2. Any declared feature that no longer matches code.
3. Material user-facing code capabilities absent from the ledger.
4. Coverage hints only; hand off skill-ownership conclusions to `skill-coverage-synthesis`.
5. A coverage receipt listing inspected entry points, omissions, and confidence.

Rules: do not modify files, do not delegate, do not run repository code/tests/builds, and do not use
the network. Report only evidence in the owned scope.

## Draft outcomes and handoffs

- The ledger contains 138 rows, but its `coverage` hash predates source and skill-catalog changes.
- Its singular canonical-`pack` schema is violated by composite and pseudo-area values such as
  `brave/ground/tavily`, `multiple`, and `ot_context/ot`.
- Confirmed stale examples/contracts include removed Direct CLI commands, Webfetch
  `max_download_bytes` as a call kwarg, Localhist `keep_days`, missing Context7 `library_name`,
  removed knowledge CLI options, and invalid arbitrary-dict `ctx.write` calls.
- Code-backed candidate rows include cross-platform bootstrap installers, isolated persistent
  extension workers, Localhist protected force-include validation, and destructive-capable run-tool
  annotations.
- Related spec drift was handed to synthesis: MCP discoverability still specifies
  `onetool://...` resources and `destructiveHint=false`, while runtime uses `ot://...` and correctly
  marks the universal run surface destructive-capable.
- These observations remain audit provenance only; the cross-scope feature-ledger validation issue
  was rejected after the user's authority clarification.

## Coverage receipt

- Assignment: `feature-ledger-audit`
- Inspected: all 138 feature rows, `features/feature-tracking.md`, Git changes from the recorded
  coverage hash, feature-linked CLI/config/server/executor/proxy/meta/context/direct/pack entry
  points, installer sources, and current MCP discoverability/extension specs.
- Checks run: static source searches, file inspection, and Git metadata only.
- Rejected issue:
  `skill-coverage-synthesis-requirements-specs-feature-ledger-unvalidated.md`.
- Handoffs: code-backed skill-ownership observations to `skill-coverage-synthesis`; detailed pack
  behavior to `pack-runtime-audit`.
- Not inspected: tests, fixtures, generated reference bodies, archived changes, runtime behavior,
  builds, network services, and deep internal helper behavior.
- Coverage confidence: high for inventory and stale contracts; medium-high for candidate feature
  granularity because the current schema has no cross-pack/platform area type.
