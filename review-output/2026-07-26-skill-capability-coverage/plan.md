# OneTool Skill Capability Coverage Review

> Post-review scope correction: the user clarified that `features/features.yaml` is
> non-authoritative historical/changelog tracking only. Its inspection below was an audit aid, not
> an endorsement of any implementation, catalog, generator, validator, test, build, or release
> dependency.

## Review contract

- Run ID: `2026-07-26-skill-capability-coverage`
- Goal: inventory current user-facing OneTool capabilities from the feature ledger and code, map
  each capability to current or proposed skill/help coverage, and identify distinct additional
  skills that require user approval.
- Reviewed revision: `528cac463d21f3b510757e106d31ad310591d56b` (dirty)
- Known dirty state at start: untracked
  `openspec/changes/pack-guidance-help-and-setup/`, created for this session before the read-only
  review began.
- Risk priorities: missing high-value workflows, shallow tool-list-only guidance, invisible
  platform/CLI capabilities, unsafe setup or proxy advice, duplicated sources of truth, and beta
  capability leakage into skills.
- Review depth: repository-wide static survey with standard-depth checks at public entry points.
- Commands authorized: static file discovery, text search, source inspection, and Git metadata
  only. No tests, builds, task runners, application entry points, package installation, or network
  access.
- Agent budget: orchestration agent plus three concurrent read-only assignments.
- Output boundary: only this run directory may be written during the review.

## Initial inventory

- Historical feature-tracking input: `features/features.yaml`; its own documentation called it
  authoritative, but the user explicitly superseded that claim after the audit.
- Runtime layers: `src/ot/` (143 files), `src/onetool/` (6 files), `src/ottools/` (18 files),
  `src/otutil/` (56 files), `src/otdev/` (48 files), and the bundled shared runtime under
  `packages/onetool-pack/`.
- Current skill catalog: 20 skill directories under `skills/`; `ot-ask` and `ot-ref` also contain
  generated/reference material.
- Canonical developer routing: `dev/index.md`, `dev/agents/hints.md`,
  `dev/agents/project-map.md`, and `dev/project/guides/index.md`.
- Proposed coverage change: `openspec/changes/pack-guidance-help-and-setup/`.

## Dimensions

- `requirements-specs`: whether feature-ledger and code-backed capabilities have an explicit,
  coherent skill/help obligation.
- `documentation-dx`: whether an agent can discover when and why to use the capability, perform
  the workflow safely, and verify success.
- `architecture-boundaries`: whether skill ownership follows meaningful user workflows without
  duplicating runtime reference material or hiding cross-pack/platform boundaries.
- `security-privacy`: whether setup, proxy, secrets, network, mutation, and beta boundaries are
  represented in the proposed guidance.

## Scope manifests

### feature-ledger — Declared product feature ledger

- Purpose: enumerate every surviving feature declared by the project and verify it against its
  named implementation area.
- Primary paths: `features/features.yaml`, `features/feature-tracking.md`, feature-linked public
  specifications and reference indexes.
- Explicit exclusions: generated reference bodies, historical changes, fixtures, and archived
  specifications.
- Entry points: each feature row's `pack`, description, and examples.
- Dependencies allowed for context: named runtime modules and the proposed OpenSpec change.
- Risk signals: ledger coverage hash predates reviewed revision; rows include platform surfaces
  that are not ordinary packs.

### pack-runtime — Built-in pack capabilities

- Purpose: identify the strategic workflows and distinctive powers implemented by core, util, and
  dev packs.
- Primary paths: `src/ottools/`, `src/otutil/tools/`, `src/otdev/tools/`, and
  `packages/onetool-pack/src/otpack/`.
- Explicit exclusions: vendored assets, generated files, large templates, fixtures, and tests.
- Entry points: pack declarations, exported tool functions, typed config, and requirement metadata.
- Dependencies allowed for context: shared utilities under `src/ot/`.
- Risk signals: 28 declared packs, heterogeneous requirements, optional providers, and several
  workflow-heavy packs whose value exceeds a flat tool list.

### platform-surfaces — Core runtime, CLI, direct API, configuration, and proxy

- Purpose: identify user-facing capabilities not represented as ordinary pack skills.
- Primary paths: `src/ot/`, `src/onetool/`, root configuration/packaging metadata.
- Explicit exclusions: internal helpers with no agent/operator decision surface, tests, caches, and
  generated templates except as evidence of a public setup flow.
- Entry points: `run`, `ot.*`, `onetool serve`, `onetool init`, `onetool direct`, `onetool kb`,
  proxy lifecycle, config/secrets/security, resources/prompts, and install/distribution.
- Dependencies allowed for context: feature ledger, architecture docs, and proposed OpenSpec.
- Risk signals: high-value direct/CLI/setup capabilities may be invisible in pack-owner mapping.

### skill-system — Current and proposed skills, runtime help, and DRY generation

- Purpose: map every capability to an existing skill, a proposed rewrite/help topic, an intentional
  exclusion, or an uncovered workflow.
- Primary paths: `skills/`, `src/otdev/docsgen/`, relevant `dev/project/guides/`, and
  `openspec/changes/pack-guidance-help-and-setup/`.
- Explicit exclusions: unrelated OpenSpec changes and user-facing prose not tied to skill/help
  discovery.
- Entry points: skill metadata, ownership/profile declarations, router routes, help topics, managed
  blocks, validators, and docs generators.
- Dependencies allowed for context: all other scopes read-only.
- Risk signals: current skills are intentionally compact, ownership/profiles are duplicated, and
  the proposed design must prevent reference duplication while increasing strategic guidance.

## Assignment matrix

| Assignment | Owned scope | Dimensions | Depth | Risk | Status |
|---|---|---|---|---|---|
| `feature-ledger-audit` | `feature-ledger` | requirements-specs, documentation-dx | standard | Ledger is declared source of truth but may omit newer or non-pack surfaces | completed |
| `pack-runtime-audit` | `pack-runtime` | requirements-specs, documentation-dx, security-privacy | standard | Large capability surface and optional workflow boundaries | completed |
| `platform-surface-audit` | `platform-surfaces` | requirements-specs, architecture-boundaries, security-privacy | standard | Platform features lack natural pack ownership | completed |
| `skill-coverage-synthesis` | `skill-system` plus cross-scope synthesis | all selected dimensions | deep | Final mapping and new-skill threshold require global evidence | completed |

The matrix is intentionally scope-major. Cross-scope ownership and final candidate decisions remain
with `skill-coverage-synthesis`; workers hand off rather than duplicate those findings.

## Exclusions and limitations

- No runtime behavior was executed; claims are based on static source, metadata, specifications, and
  documentation evidence.
- Tests are context only if needed to resolve a contract, not a reviewed scope.
- Vendored ELK assets, generated tool indexes, lock files, caches, build output, snapshots, and
  large templates are excluded.
- Beta `console` is inventoried for coverage accounting but, per approved decision, must have no
  skill or router coverage.

## Status

- Repository instructions and all review-skill references loaded.
- Initial inventory corrected to include the bundled `packages/onetool-pack/` workspace member.
- All assignments and synthesis completed. One cross-scope issue was accepted and the complete
  coverage report was written to `summary.md`.
