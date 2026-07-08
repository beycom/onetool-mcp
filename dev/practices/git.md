# Git Workflow

Reusable git workflow for short-lived branches, conventional commits, explicit merge commits, and annotated release tags.

---

## Commit Format

```
<type>(scope): <description>
Ref: #123
```

- 50-72 chars ideal, can be longer
- Second line for issue reference only (optional)
- No message body
- Imperative mood: "add" not "added"
- No capital first letter, no trailing period

---

## Types

| Type | Use For |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code restructure |
| `perf` | Performance |
| `docs` | Documentation |
| `test` | Tests |
| `build` | Build system |
| `ci` | CI/CD |
| `chore` | Maintenance |
| `style` | Code style |

---

## Scopes

Scopes are project-specific. This repository uses:

**Core**: `config`, `cli`, `serve`, `executor`, `security`, `stats`, `logging`, `prompts`, `registry`, `paths`, `openspec`

**Tools** (use `tool:` prefix): `tool:brave`, `tool:ripgrep`, `tool:excel`, `tool:db`, `tool:diagram`, `tool:mem`, etc.

**Other**: `deps`, `release`, `demo`, `dx`, `ci`, `build`, `docs`

Omit scope for project-wide changes.

For comprehensive scope reference, see [commit-scopes.md](commit-scopes.md).

---

## Scope Decision Tree

If a change touches multiple areas, use the primary focus:
- Core execution flow → `executor`
- Security rules → `security`
- CLI display → `cli`
- Data collection → `stats`
- Tool registration → `registry`

---

## Examples

```
feat(tool:brave): add news search endpoint
fix(config): resolve include paths from ot_dir
refactor(executor): simplify tool loading
feat(config): add compact array format; update security template
```

---

## Branch Naming

| Pattern | Example | Description |
|---------|---------|-------------|
| `main` | `main` | Main development branch |
| `feature/{name}` | `feature/config-refactor` | Feature branches |
| `fix/{name}` | `fix/auth-bug` | Bug fix branches |
| `remove/{name}` | `remove/aws-pack` | Removal branches for deleting packs, tools, integrations, or other owned surfaces |
| `release/{version}` | `release/1.0.0` | Release preparation branches |

Use `remove/{name}` for intentional deletions that should be reviewed as a named change. This keeps removal work distinct from ordinary refactors and avoids ambiguous temporary names like `wip/remove-{name}`.

---

## Merge Strategy

### Feature to Main

```bash
git checkout main
git pull origin main
git merge feature/branch-name --no-ff -m "Merge feature/branch-name for v1.0.0rc3"
```

Use `--no-ff` to create explicit merge commits for feature branches. This preserves the feature branch history in the commit graph.

### Fast-Forward Only

Use `--ff-only` for simple updates where main hasn't diverged.

---

## Tag Naming

Version tags follow semantic versioning with `v` prefix:

| Pattern | Example | Description |
|---------|---------|-------------|
| `v{major}.{minor}.{patch}` | `v1.0.0` | Stable release |
| `v{major}.{minor}.{patch}rc{n}` | `v1.0.0rc3` | Release candidate |
| `v{major}.{minor}.{patch}b{n}` | `v1.0.0b1` | Beta release |
| `{descriptive-name}` | `pre-rebrand-merge` | Snapshot/milestone tag |

Annotated tags (`-a`) with `v` prefix: `v1.0.0`, `v1.0.0rc3`, `v1.0.0b1`

---

## Release Workflow

This is the generic git portion of a release. Project packaging, publishing, and validation steps belong in the project release runbook. For this repository, see [OneTool Release & Publish Guide](../project/guides/release.md).

1. Ensure feature branch is clean (no uncommitted changes)
2. Merge feature branch to main with `--no-ff`
3. Tag the release: `git tag -a v1.0.0rc3 -m "Release candidate 3 for version 1.0.0"`
4. Push main and tags: `git push origin main && git push origin v1.0.0rc3`

**Tag format:**
- Use annotated tags (`-a`) for all version releases
- Use descriptive messages that include the release type
- Always push tags explicitly after pushing main

---

## Branch Hygiene

- Delete feature branches after merging to main
- Delete merged `remove/{name}` branches after the removal is stable, or rename them to `archive/remove-{name}` when keeping them as historical breadcrumbs
- Keep main clean and deployable at all times
- No force pushes to main
- Feature branches should be short-lived (days, not weeks)

---

**Related:**
- [Commit Scopes](commit-scopes.md) - Comprehensive scope reference
