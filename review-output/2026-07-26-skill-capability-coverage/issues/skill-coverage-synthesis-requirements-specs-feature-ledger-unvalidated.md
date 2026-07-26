# Rejected: feature ledger guidance coverage validation

## Disposition

Rejected after review. The user clarified that `features/features.yaml` is non-authoritative
historical/changelog tracking that may be removed. It MUST NOT be used by runtime code, typed
catalogs, generators, validators, test oracles, builds, or release gates. The observations below
remain audit provenance only and are not an implementation issue.

## Metadata

- Assignment: `skill-coverage-synthesis`
- Review run: `2026-07-26-skill-capability-coverage`
- Reviewed revision: `528cac463d21f3b510757e106d31ad310591d56b` (dirty)
- Severity: `medium`
- Confidence: `high`
- Review dimension: `requirements-specs`
- Review scope: `feature-ledger`
- Kind: `gap`
- Tags: `repo-review`, `dimension:requirements-specs`, `scope:feature-ledger`,
  `severity:medium`, `kind:gap`, `cross-scope`

## Problem

`features/features.yaml` is declared to contain every current surviving feature, but neither its
source-coverage hash nor its feature-area-to-guidance relationship is checked against the current
runtime and skill catalog. Removed commands can therefore remain advertised, and non-pack
capability areas such as CLI, config, direct API, security, packaging, and deployment have no
machine-checked skill/help/developer-guide disposition.

## Impact

Agents and maintainers can plan against capabilities that no longer exist, while a pack-oriented
skill coverage check still passes. This creates repeated rediscovery during skill audits and allows
future platform features to ship without an intentional agent-guidance decision. The impact is
material but bounded because code/reference inspection can detect the drift manually.

## Evidence

- `features/feature-tracking.md:3` — declares the YAML file the source of truth for every current,
  surviving OneTool feature.
- `features/features.yaml:4` — records coverage only through `cb502fd0`, while the reviewed revision
  is `528cac463d21f3b510757e106d31ad310591d56b`.
- `features/features.yaml:557` — claims `onetool direct` provides
  `run/repl/start/stop/status/logs/list/search/help`.
- `features/features.yaml:567` — repeats the removed direct CLI discovery and lifecycle commands.
- `src/onetool/cli_commands/direct_app.py:190` — the current direct Typer application registers
  only the `run` command.
- `src/otdev/docsgen/metadata.py:19` — the current guidance catalog begins with runtime-pack
  records and contains no feature-ledger or non-pack capability-area coverage model.
- `src/otdev/docsgen/skill_catalog.py:53` — validation checks runtime packs, owners, skills, and
  profiles, but never reads the feature ledger.
- `git log --oneline cb502fd0..528cac46` — shows source and product-surface changes after the
  recorded coverage hash, including direct/console/local-history changes and the skill catalog.

## Historical reproduction

1. Compare the direct CLI claims at `features/features.yaml:557` and
   `features/features.yaml:567` with registered commands in
   `src/onetool/cli_commands/direct_app.py`.
2. Search the current docs/skill generators for `features.yaml`; no validator composes it with the
   skill catalog.

## Required direction

Use current code and validated public interfaces as authority. Audit leads may be checked manually
against those sources, but no implementation work may parse, normalize, validate, generate from,
or depend on the historical feature file.
