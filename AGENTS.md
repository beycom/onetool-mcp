
Read dev/agents/hints.md for quick reference (commands, rules, project structure).
Read dev/agents/project-map.md for detailed project structure.
Read dev/index.md for complete dev docs navigation.
Read dev/project/guides/index.md before creating tools — it links to creating-tools.md, which covers shared utilities to check before implementing common patterns (HTTP clients, caching, truncation, etc.).

## Commands

Use `just` (not `make`) for project commands:

```bash
just check    # Run all checks (lint, type, test)
just test     # Run tests
just lint     # Run linters
```

## No Backward Compatibility

**Never add backward-compatible fallbacks unless explicitly asked.**

- Removed API values, parameter names, or config keys must raise a clear error — not silently work
- No aliases, shims, or "treat old value as new value" logic
- No `_deprecated`, `_legacy`, or transitional code paths
- When something is renamed or removed, delete it — do not keep the old name working

Examples of what NOT to do:
- Old `info="list"` silently treated as `"full"` → wrong; raise `ValueError` immediately
- Renamed parameter kept working under old name → wrong; raise `TypeError` with a clear message
- Removed config key silently ignored → wrong; raise a config error

The goal is a simple, clean codebase. Backward compat adds hidden complexity and makes bugs harder to find.

## Testing Constraints

- Never use `example.com` in tests or examples — it does not exist.
  Use realistic tool calls or omit URLs entirely.

## OpenSpec Workflow

Use `/opsx:new` for changes that define new user-facing behaviour or modify
existing contracts:

✅ Requires OpenSpec:
- New tool packs or extras ([dev], [util])
- New CLI commands or flags
- Changes to config format, file locations, or schema
- Changes to MCP tool interface or server behaviour
- New registry or tool discovery mechanism

❌ No OpenSpec needed:
- Bug fixes and correctness improvements
- Performance improvements
- Adding or improving tests
- Internal refactors with no behaviour change
- Cherry-picking improvements from other branches
- Documentation and spec updates
- Build/tooling changes (pyproject.toml, justfile)
