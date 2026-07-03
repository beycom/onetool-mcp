# Conventional Commit Scopes

Quick reference for commit messages in this project.

**Format:**
```
<type>(scope): <description>
Ref: #123
```

**Notes:**
- Description: 50-72 chars ideal, can be longer if needed
- Second line for issue reference only (optional)
- NO message body

## Core Systems

| Scope | Description | Examples |
|-------|-------------|----------|
| `config` | Configuration system | Loader, models, secrets, includes |
| `cli` | Command-line interface | onetool CLI, arg parsing |
| `serve` | MCP server | Server startup, tool discovery |
| `proxy` | MCP proxy/client | Client connections, tool routing |
| `executor` | Execution engine | Runner, validator, tool loader |
| `security` | Security system | AST validation, allowlists |
| `stats` | Statistics | Collection, persistence, reporting |
| `logging` | Logging system | Log formatting, verbosity |
| `prompts` | Prompts system | Prompt loading, templates |
| `registry` | Tool registry | Tool discovery, registration |
| `paths` | Path resolution | Path utilities, OT_DIR handling |
| `openspec` | OpenSpec integration | Proposals, specs, archiving |

## Tool Packs (use `tool:name`)

| Scope | Pack | Description |
|-------|------|-------------|
| `tool:brave` | brave | Brave web/news search |
| `tool:context7` | context7 | Library documentation |
| `tool:convert` | convert | Document conversion |
| `tool:db` | db | Database operations |
| `tool:diagram` | diagram | Diagram generation |
| `tool:excel` | excel | Excel operations |
| `tool:file` | file | File I/O operations |
| `tool:ground` | ground | Grounding search |
| `tool:transform` | transform | LLM transform tool |
| `tool:ot` | ot | Meta/introspection tools |
| `tool:package` | package | Package info (npm, pypi) |
| `tool:ripgrep` | ripgrep | Fast code search |
| `tool:scaffold` | scaffold | Tool scaffolding |
| `tool:webfetch` | webfetch | Web fetch |

## Other Scopes

| Scope | When to Use |
|-------|-------------|
| `deps` | Dependency updates (package versions) |
| `release` | Release prep (version bumps, changelogs) |
| `demo` | Demo/example code |
| `dx` | Developer tooling (scripts, workflows) |
| `ci` | CI/CD changes (GitHub Actions) |
| `build` | Build system (uv, ruff, mypy config) |
| `docs` | Documentation (when not tool-specific) |

## Commit Types

| Type | Use For | Example |
|------|---------|---------|
| `feat` | New feature | `feat(tool:brave): add news search endpoint` |
| `fix` | Bug fix | `fix(config): resolve include paths from ot_dir` |
| `refactor` | Code restructure | `refactor(config): simplify to global-only` |
| `perf` | Performance | `perf(tool:ripgrep): reduce token usage by 50%` |
| `docs` | Documentation | `docs(readme): update installation instructions` |
| `test` | Tests | `test(config): add compact array format test` |
| `build` | Build system | `build: update uv to 0.5.0` |
| `ci` | CI/CD | `ci: update release workflow` |
| `chore` | Maintenance | `chore(deps): update pydantic to 2.12` |
| `style` | Code style | `style: fix ruff formatting issues` |

## Guidelines

### DO:
✅ Use type/scope of the MOST IMPORTANT change
✅ List multiple changes in description (most important first)
✅ Use imperative mood: "add" not "added"
✅ Use semicolons to separate multiple changes
✅ Omit scope if change is project-wide
✅ Add `Ref: #123` on second line if there's an issue

### DON'T:
❌ Don't add body text (description line + optional ref line only)
❌ Don't use past tense ("added", "fixed")
❌ Don't capitalize first letter of description
❌ Don't end description with a period

## Scope Decision Tree

**If change touches multiple areas, use PRIMARY focus:**

- Core execution flow → `executor`
- Security rules → `security`
- Display/formatting in CLI → `cli`
- Data collection → `stats`
- Tool registration → `registry`

**Examples:**
- `fix(cli): display stats correctly` ← CLI display bug
- `fix(stats): calculate metrics correctly` ← Stats calculation bug
- `feat(executor): add parallel tool execution` ← Execution engine feature
- `feat(security): add new builtin allowlist` ← Security config

## Examples

### Single Change ✅

```
feat(tool:brave): add news search endpoint
fix(config): resolve include paths from ot_dir not config_dir
refactor(config): remove project-level configuration support
perf(tool:ripgrep): reduce token usage by 50%
test(config): add compact array format test
docs(readme): update installation for uv
chore(deps): update pydantic to 2.12
```

### Multiple Changes (most important first) ✅

```
feat(config): add compact array format; update security template
fix(tool:brave): prevent racing; add retry logic; improve error handling
refactor(config): simplify loader; remove inheritance; flatten includes
docs: update readme; fix typos; add examples
```

### With Issue Reference ✅

```
fix(tool:brave): prevent racing of requests; add retry logic
Ref: #123
```

### Bad Examples ❌

```
❌ Added news search and fixed a bug
   (past tense, no scope/type)

❌ feat(tool:brave): Add news search endpoint.
   (capitalized, has period)

❌ feat(tool:brave): added news search
   (past tense)

❌ fix: bug fixes
   (too vague - what was fixed?)

❌ feat: stuff
   (meaningless description)
```

## When to Omit Scope

Omit scope for project-wide changes:
```
docs: update all tool documentation
chore: update all imports to new structure
build: update uv to 0.5.0
style: apply ruff formatting
```

## Using /p:stage

1. Make your changes
2. Run `/p:stage`
3. Agent analyzes changes and suggests **single-line** message
4. Review and commit

The agent will suggest the appropriate type and scope based on the files you changed!
