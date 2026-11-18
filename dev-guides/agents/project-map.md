# Project map

All code is in `src/onetool`. Follow the nearest owning module rather than adding a new framework.

| File | Owns | Main tests |
| --- | --- | --- |
| `config.py` | Safe YAML, strict models, environment references and paths | `test_config.py` |
| `cli.py`, `__main__.py` | argparse, explicit config path and exit codes | `test_cli.py` |
| `gateway.py` | Native providers/CodeMode, namespaces, deadlines, status and auth wiring | `test_gateway.py`, `test_auth.py` |
| `operations.py` | Admission, drain cancellation, reload and restart | `test_operations.py` |
| `results.py` | Inline cap, private files, hashes and eviction | `test_results.py`, `test_operations.py` |
| `diagnostics.py` | JSON events, redaction, rotation and record cap | `test_diagnostics.py` |
| `scripts/release.py` | Local version and artifact/dependency inventory | [Release](../project/release.md) |

Tests live under `tests/`; one [fixture server](../../tests/fixtures/fixture_server.py) supports stdio and loopback HTTP. Installed checks are under `tests/installed/`. [Documentation tests](../../tests/test_docs.py) run examples and check local links.

When private planning is linked, start with the [V4 summary](../../planning/features/backlog/[gateway]-v4/summary.md). The bundle holds [tasks](../../planning/features/backlog/[gateway]-v4/tasks.md), [evidence](../../planning/features/backlog/[gateway]-v4/evidence.md), [POC entry point](../../planning/features/backlog/[gateway]-v4/pocs/README.md) and [upstream gap drafts](../../planning/features/backlog/[gateway]-v4/pocs/upstream-gaps.md). These links are optional outside the source workspace.

[Architecture](../project/architecture.md) explains composition; user-facing behavior belongs in [docs](../../docs/python.md). Build/test commands come from `justfile` and `pyproject.toml`.
