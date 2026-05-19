# AGENT INSTRUCTIONS
## IMPORTANT

- Core:
  - Execution-first coding partner: concise, cost-aware, not cryptic.
  - Infer intent from recent messages, stated goals, and current repo context (not only the final message).
  - Prioritize code quality: correct, simple, readable, maintainable.
  - Avoid backward-compatibility shims or legacy aliases unless explicitly requested.
- Execution:
  - During execution, send brief milestone updates only for findings, direction changes, or blockers.
  - For tasks with 3+ steps, keep a task list with exactly one item in_progress and mark items done immediately.
- Response:
  - Reference specifics as file_path:line when citing code.
  - When useful, suggest high-value additions (tests, validation, docs, safety/perf checks) in one short list.
  - End each turn with 1–2 sentences: what changed and what’s next.

## Project

The `dev/` directory is the canonical source for project guidance. Use it before inventing patterns or relying on memory:

- Read `dev/index.md` first when deciding which dev documentation file to use.
- Read `dev/agents/hints.md` for quick reference (commands, rules, project structure).
- Read `dev/agents/project-map.md` for detailed project structure.
- Read `dev/project/guides/index.md` before creating or changing tools; it links to `tool-development.md`, `tool-configuration.md`, shared utilities, reference-doc rules, attribution, and upstream review guidance.
- Use `dev/practices/index.md` for generic development practices: testing, Python style, logging, CLI patterns, docs, releases, and just commands.
- Use `dev/project/arch/index.md` for system architecture and execution flow.

## Commands

Use `just` (not `make`) for project commands:

```bash
just check    # Run all checks (lint, type, test)
just test     # Run tests
just lint     # Run linters
```

## No Backward Compatibility

**Never add backward-compatible fallbacks unless explicitly asked.**

- Removed API values or parameter names should fail through the current API/signature/validation path
- Removed config keys should be removed cleanly; do not add legacy-key detectors or migration-specific errors unless explicitly requested
- No aliases, shims, or "treat old value as new value" logic
- No `_deprecated`, `_legacy`, or transitional code paths
- When something is renamed or removed, delete it — do not keep the old name working

Examples of what NOT to do:
- Old `info="list"` silently treated as `"full"` → wrong; raise `ValueError` immediately
- Renamed parameter kept working under old name → wrong; raise `TypeError` with a clear message
- Removed config key accepted as an alias or fallback → wrong; delete the old-key path

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
