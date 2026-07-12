# OneTool Release & Publish Guide

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
- Copy/paste the generated entry into CHANGELOG.md, then edit it to match the
  changelog conventions below

### Changelog conventions

Every entry in `CHANGELOG.md` follows the same format (normalized 2026-07-12; keep
new entries consistent):

- **Entry heading**: `## [x.y.z] - YYYY-MM-DD`, entries separated by `---`.
- **Sections** (`###`, title case), in this order, using only these names —
  omit any that don't apply:
  1. `Highlights` — the release announcement: lead with the stories that sell the
     release (the homepage/README may link here).
  2. `Breaking Changes` — every break, each with a one-line migration note. A
     single merged `Removed` list of deleted surfaces lives here as a sub-bullet.
  3. `New Tool Packs`
  4. `New Features`
  5. Topical improvement sections — `Tool Improvements`, or per-area headings such
     as `Memory (\`mem\`) Improvements`, `Whiteboard Improvements`, `Direct API`.
  6. `Configuration` / `Deployment`
  7. `Fixed`
  8. `Changed` — non-breaking behavior changes only; anything requiring user
     action belongs in `Breaking Changes`.
  9. `Documentation`
- **Bullet style**: `**Feature name** — description.` Em-dash (`—`, not `-`),
  sentence case, closing period. Backticks around pack/tool/config names.
- **Wording**: user-facing prose, not commit messages — no "add X", no internal
  verification notes (file paths, "verified against src/"), no drafting residue.
  Use current pack names as of that release.

---

## Step 2: Check

```bash
just install-locked
just release::check
```

- Recreates the release validation environment from the lockfile
- Runs lint, typecheck, and all tests
- Scans for secrets with gitleaks
- Builds docs (strict mode to catch broken links)
- Runs `/p-test-explore sanity.md retest all` via the Codex TUI

---

## Step 2.5: Direct-run sanity gate

Confirm the Direct API actually executes tool calls inside a live root process before
publishing. **This gate must pass before `just release::publish` is invoked.**

Start a root process — either `onetool serve` or a running direct host with
`direct.host.enabled: true` — then run the seven probe commands from
`tests/explore/test-cli.md:122-128` against it (with `$OT_DIR` set to the parent Direct
API auth-key directory and `--port` matching the running host):

```bash
onetool direct run --ot-dir "$OT_DIR" --port 8765 "ot.version()"
onetool direct run --ot-dir "$OT_DIR" --port 8765 "ot.debug()"
onetool direct run --ot-dir "$OT_DIR" --port 8765 "ripgrep.search(pattern='TODO', path='.')"
onetool direct run --ot-dir "$OT_DIR" --port 8765 "mem.write(topic='tmp/test/cli-runtime', content='direct probe', category='note'); mem.read(topic='tmp/test/cli-runtime'); mem.delete(topic='tmp/test/', confirm=True)"
onetool direct run --ot-dir "$OT_DIR" --port 8765 --format json "ot.version()"
onetool direct run --ot-dir "$OT_DIR" --port 8765 --format yml "ot.version()"
echo 'ot.version()' | onetool direct run --ot-dir "$OT_DIR" --port 8765 -
```

The probes are: `ot.version()`; `ot.debug()`; a `ripgrep.search(...)` call; a
`mem.write` / `mem.read` / `mem.delete` sequence; `--format json` and `--format yml`
variants of `ot.version()`; and the stdin-dash form.

Verify (per `tests/explore/test-cli.md`'s "Verify" list):

- calls execute in the running root process
- real pack calls route through the root registry, not only `ot.*` introspection
- output formats are honored
- stdin command input works

If any probe fails, do not publish — resolve it first.

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

---

## Verification Links

After release, verify at:
- PyPI: https://pypi.org/project/onetool-mcp/
- MCP Registry: https://registry.modelcontextprotocol.io
- GitHub: https://github.com/beycom/onetool-mcp/releases
- Docs: https://onetool.beycom.online
