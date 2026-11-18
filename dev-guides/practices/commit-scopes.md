# Commit scopes

Choose the primary behavior affected, not every edited file. These scopes follow V4 ownership and recent history; they are conventions rather than validation rules.

| Scope | Use |
| --- | --- |
| `config` | YAML schema, loading, interpolation and paths |
| `cli` | Argument parsing and command behavior |
| `gateway` | Composition, routing, CodeMode, lifecycle and auth wiring |
| `logging` | Operational events and redaction |
| `results` | Inline output and file recovery |
| `release` | Versions, installers and artifact inventory |
| `deps` | Dependency/lock updates |
| `build`, `ci` | Recipes, packaging and CI |
| `docs` | User/developer guidance |

Examples: `fix(gateway): route calls to the selected backend`, `docs: reorganize developer guides`. Keep independent changes separate, but do not split a behavior from the tests or config it needs.
