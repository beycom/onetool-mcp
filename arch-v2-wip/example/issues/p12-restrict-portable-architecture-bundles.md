# P12 — Restrict portable architecture bundles to owned source files

## Problem

Bundling a workspace directory includes every top-level file. A portable bundle can therefore include `.env`, credentials, notes, or unrelated documents.

Generated artifacts are identified through any root manifest without validating its owner, allowing an unrelated manifest to classify arbitrary contained paths as generated architecture artifacts.

## Expected

Bundle only the selected architecture source and explicitly referenced architecture resources:

- workspace YAML or Excel source;
- recognized `views`, `styles`, and `assets` resources;
- manifests owned by the architecture operation; and
- owned generated artifacts only when `include_generated=true`.

Reject or ignore unrecognized manifests. Never include arbitrary top-level files implicitly.

## Actual

`portable.py::_bundle_sources` collects every top-level file with `root.iterdir()`. `_manifest_owned` accepts manifests without checking their `owner`.

## Acceptance Criteria

- `.env`, credentials, arbitrary notes, and unrelated manifests are excluded.
- A recognized architecture manifest must have the expected owner and schema.
- Containment and symlink protections remain enforced.
- Bundles stay deterministic.
- Tests cover malicious manifests, secret-like files, nested assets, generated inclusion, and user-owned files.
- Skill and reference documentation describe the exact inclusion policy.

## Context

Review:

- `src/otdev/tools/_arch/v2/portable.py::_manifest_owned`
- `src/otdev/tools/_arch/v2/portable.py::_bundle_sources`
- `tests/otdev/integration/tools/test_arch_v2_portable.py`
- `skills/ot-arch/SKILL.md`

Use `$p-fix`; do not introduce compatibility handling for previously over-inclusive bundles.
