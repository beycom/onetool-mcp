# AGENT INSTRUCTIONS

## Important

- Core:
  - Execution-first coding partner: concise, cost-aware, not cryptic.
  - Infer intent from recent messages, stated goals, and current repo context.
  - Prioritize code quality: correct, simple, readable, maintainable.
  - No backward-compatibility shims or legacy aliases unless explicitly requested.
- Execution:
  - Send brief milestone updates only for findings, direction changes, or blockers.
  - For tasks with 3+ steps, keep a task list with exactly one item in progress.
- Response:
  - Reference specifics as file_path:line when citing code.
  - End each turn with 1–2 sentences: what changed and what's next.

## Project

OneTool V4 is a small MCP gateway: one YAML file, upstream MCP servers proxied through FastMCP, and Python orchestration through FastMCP CodeMode. V4 replaces the V3 tool platform. It owns no tool packs.

The plan is the source of truth. Read it before changing anything:

- `planning/features/backlog/[gateway]-v4/summary.md` first, then `design.md`, `operations.md`, `tasks.md` and `validation.md`.
- `planning/features/backlog/[gateway]-v4/reviews/stress-test-review.md` explains why the plan is small. Do not reintroduce what it removed.
- Log task evidence in `planning/features/backlog/[gateway]-v4/evidence.md`. Keep POC scripts in `planning/features/backlog/[gateway]-v4/pocs/`.

Until task T03 lands, this branch still contains the V3 source, `dev/`, `docs/` and `openspec/`. They describe the old product. Do not follow their guidance or extend them. T03 deletes them. The V3 source stays readable at the `archive/pre-v4-main` branch.

## Rules for V4 code

- Upstream first. Before writing a module, check what FastMCP already does. A gap becomes an upstream issue or pull request where possible. A local stand-in is small, links the upstream issue, and is deleted when upstream ships.
- Never reach into private FastMCP or MCP SDK attributes.
- Prove unproven upstream behavior with a POC script before building on it.
- Production budget is 2,000 to 3,500 lines. Docs budget is 800 user lines and 500 developer lines.
- One package, `src/onetool`. Standard-library argparse and logging. No service locator, plugin loader, module-level runtime state or duplicate sync and async APIs.
- Never replay a tool call automatically. Report an interrupted call's outcome as unknown.
- Never log code, arguments, results, header values or env values.

## No backward compatibility

- Removed API values, parameter names and config keys fail through the normal validation path.
- No aliases, shims, `_deprecated` or `_legacy` paths, and no V3 config detection or migration.
- When something is renamed or removed, delete it.

## Workspace

- `planning` is a symlink to the private sibling repository `../onetool-mcp-planning`. It is ignored here. Never `git add` planning content in this repository. Commit planning only inside that repository, with `just planning-commit`, and only when asked.
- `.codex` is shared from the main checkout and `.claude` links to it. Skills live in `planning/skills`.
- Work on `feature/v4` or a child branch created with `just worktree-new <branch> feature/v4`. Never commit on `main`. Push only when asked.
- The old checkout at `/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp` and its worktrees are preserved. Never modify, clean or delete them.

## Commands

Use `just`, not `make`:

```bash
just check    # all checks
just test     # tests
just lint     # linters
```

## Testing constraints

- Never use `example.com` in tests or examples. Use the fixture servers or omit URLs.
- Test through a real MCP client against the fixture servers. Test what OneTool owns, not FastMCP's behavior.
