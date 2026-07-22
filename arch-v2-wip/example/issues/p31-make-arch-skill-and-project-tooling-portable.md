# P31 — Make architecture skill and project tooling portable

## Problem

Project tooling contains machine-specific paths, and the new `ot-arch` skill is not included in the project skill manifest or hash metadata.

`just skills-install` depends on an absolute local OneSkill checkout and performs destructive copy/move operations around `ot-ref`. `oneskill.lock.yaml` also records an absolute local source path.

## Expected

- Make project commands work from any checkout location.
- Resolve OneSkill through a declared, reproducible project mechanism.
- Include `ot-arch` in the skill manifest, lock, and hashes.
- Install project skills without temporarily deleting or moving unrelated user state.
- Keep dry-run and repeat installation deterministic.

## Actual

`justfile` and `oneskill.lock.yaml` contain `/Users/gavin/...` paths. `apm.yaml` and `skills/skill-hashes.yaml` include only `ot-ref`.

## Acceptance Criteria

- No committed file contains a developer-specific absolute path.
- A clean checkout can install both `ot-ref` and `ot-arch`.
- Dry-run reports the correct actions without mutation.
- Repeated installation is idempotent.
- Failure does not remove an existing valid skill installation.
- Tooling tests or documented verification cover the supported environments.

## Context

Review:

- `justfile::skills-install`
- `apm.yaml`
- `oneskill.lock.yaml`
- `skills/skill-hashes.yaml`
- `skills/ot-arch/`
- existing OneSkill project guidance

Use `$p-fix`; keep this separate from architecture runtime implementation changes.
