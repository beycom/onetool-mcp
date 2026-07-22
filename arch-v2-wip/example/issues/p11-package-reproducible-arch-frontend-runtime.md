# P11 — Package a reproducible architecture frontend runtime

## Problem

Architecture explorer generation requires `src/otdev/tools/_arch/frontend/node_modules/.bin/vite` at runtime. The frontend check uses `npm ci`, but `package-lock.json` is globally ignored and no installed Python distribution contains the required Node dependencies or a prebuilt explorer.

A clean checkout cannot reproducibly run `just arch-frontend-check`, and an installed OneTool package cannot reliably execute `arch.generate`.

## Expected

- Commit and verify the frontend dependency lock.
- Make `just arch-frontend-check` work from a clean checkout.
- Ship a self-contained runtime asset strategy that does not depend on a developer's `node_modules`.
- Prefer a prebuilt static explorer shell with architecture data injected at generation time.
- Verify the wheel and source distribution contain every required runtime asset.
- Preserve offline execution and deterministic output.

## Actual

`frontend.py::_build_html` raises `ExplorerBuildError` unless a local Vite executable exists under the source tree.

## Acceptance Criteria

- Clean-clone frontend installation and checks pass.
- A built wheel installed into an isolated environment can generate and open an explorer without the repository checkout.
- No network access is required at generation or viewing time.
- Dependency and generated-asset versions are deterministic and documented.

## Context

Review:

- `.gitignore`
- `justfile::arch-frontend-check`
- `pyproject.toml`
- `src/otdev/tools/_arch/v2/frontend.py::_build_html`
- `src/otdev/tools/_arch/v2/likec4.py`
- `src/otdev/tools/_arch/v2/exporter.py`
- `src/otdev/tools/_arch/frontend/`

Use `$p-fix`; this is a correctness and packaging repair, not a new OpenSpec change.
