# Git

Work on `feature/v4` or a child branch created with `just worktree-new BRANCH feature/v4`. Check `git status --short` before editing or staging. Leave unrelated work untouched; never use a shared stash to move another session's changes.

Group a behavior with its source, tests, docs, config and generated lock changes. Inspect the staged diff before committing. A source commit should have passing evidence for that exact tree. Commit and push authority are separate; never infer either from a review request.

Use Conventional Commits: `type(scope): imperative description`, lower-case description, no trailing period. Types include feat, fix, refactor, perf, docs, test, build, ci and chore. Use a scope from [commit scopes](commit-scopes.md), or omit it for a project-wide change. Existing history uses this format; no message hook enforces it.

Keep feature history with an ordinary merge commit when the owner authorizes main cutover. Never commit directly on main or rewrite pushed history without explicit authorization. Version tags have a `v` prefix and are annotated; building a candidate does not create or move one automatically.

Private planning is a different Git repository. Do not stage its link or contents in source. See [workspace](workspace.md) and [release](../project/release.md).
