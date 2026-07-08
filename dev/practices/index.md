# Development Practices

Reusable development workflows and standards for Python projects using pytest, structured logging, OpenSpec-style specs, and MkDocs-style documentation. Project-specific command and release runbooks live under [OneTool Guides](../project/guides/index.md).

---

## Development Workflow

| Guide | Topic |
|-------|-------|
| [Git Workflow](git.md) | Git branching, commits, merge strategy |
| [Commit Scopes](commit-scopes.md) | Comprehensive conventional commit scope reference |
| [Spec Writing](spec-writing.md) | OpenSpec quality, scope, and bloat control |
| [Documentation Writing](docs-writing.md) | MkDocs Material features and best practices |
| [Documentation Visual Design](docs-visual-design.md) | Design system for documentation site |

---

## Code Standards

| Guide | Topic |
|-------|-------|
| [Python Style](python-style.md) | Python coding standards |
| [Testing](testing.md) | Testing strategy, markers, fixtures |
| [Logging](logging.md) | LogSpan patterns and best practices |
| [CLI Patterns](cli-patterns.md) | CLI development patterns |

---

## Quick Reference

| I want to... | See |
|--------------|-----|
| Make a commit | [Git Workflow](git.md) → Commit Format |
| Find commit scope | [Commit Scopes](commit-scopes.md) |
| Write tests | [Testing](testing.md) |
| Add logging | [Logging](logging.md) |
| Follow Python style | [Python Style](python-style.md) |
| Write or review specs | [Spec Writing](spec-writing.md) |
| Build a CLI | [CLI Patterns](cli-patterns.md) |
| Write documentation | [Documentation Writing](docs-writing.md) |
| Apply docs design system | [Documentation Visual Design](docs-visual-design.md) |

---

## Project Runbooks

| I want to... | See |
|--------------|-----|
| Use this repo's `just` commands | [OneTool Dev Commands](../project/guides/dev-commands.md) |
| Release OneTool | [OneTool Release & Publish Guide](../project/guides/release.md) |

---

**Note:** `LogSpan` and `LogEntry` are treated as reusable structured logging patterns for Python projects. OneTool-specific paths, commands, and product runbooks should live in `dev/project/`.

---

**Related:**
- [OneTool Guides](../project/guides/index.md) - OneTool-specific guides
- [Architecture](../project/arch/index.md) - OneTool architecture
