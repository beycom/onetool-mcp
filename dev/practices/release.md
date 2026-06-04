# Release & Publish Guide

Internal guide for publishing new versions of OneTool.

---

## Release Workflow

Three steps: **prepare → check → publish**

---

## Step 1: Prepare

```bash
just release::prep 1.0.0b2
```

- Updates version in `pyproject.toml` and `server.json`
- Generates changelog from git commits (via git-cliff)
- Opens `CHANGELOG.md` and `tmp/changelog-entry.md` in editor
- Copy/paste the generated entry into CHANGELOG.md

---

## Step 2: Check

```bash
just release::check
```

- Runs lint, typecheck, and all tests
- Runs Admin UI checks and build
- Rebuilds `inject.js` and fails if generated Admin UI or annotation assets are stale
- Scans for secrets with gitleaks
- Builds docs (strict mode to catch broken links)
- Runs `/p:test-explore sanity.md retest all` via `claude` CLI

---

## Step 3: Publish

```bash
just release::publish 1.0.0b2       # Dry-run (safe, shows what will happen)
just release::publish 1.0.0b2 --force  # Actually publish
```

Prompts before each step:
1. Build package artifacts (`uv build`)
2. Commit, tag, push to GitHub
3. Create GitHub release with `dist/*` artifacts attached
4. Publish to PyPI (`uv publish`) — MCP Registry validates PyPI package exists
5. Publish to MCP Registry
6. Deploy docs to GitHub Pages

---

## Helper Tasks

```bash
just release::set-version 1.0.0b2  # Update version only
just release::changelog            # Preview changelog
just release::sanity               # Run sanity tests only
```

## Individual Publish Steps

```bash
just release::build     # uv build
just release::pypi      # uv publish
just release::tag 1.0.0b2  # Commit, tag, push
just release::mcp       # mcp-publisher publish
just release::docs      # mkdocs gh-deploy
```

`just release::build` builds the Admin UI and annotation assets before `uv build`. The built wheel and sdist must include the packaged Admin UI asset tree without requiring generated `packages/admin-ui/dist/` output to be committed.

---

## Verification Links

After release, verify at:
- PyPI: https://pypi.org/project/onetool-mcp/
- MCP Registry: https://registry.modelcontextprotocol.io
- GitHub: https://github.com/beycom/onetool/releases
- Docs: https://onetool.beycom.online
