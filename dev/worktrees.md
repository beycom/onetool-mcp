# Worktrees and planning

The workspace has sibling source, private planning and worktree directories. `planning/` is an ignored link; `.codex` is shared and `.claude` links to it. Skills live in private `planning/skills`.

Work on `feature/v4` or a child created with `just worktree-new BRANCH feature/v4`. The recipe uses wtp, creates the shared links and installs the locked environment. Do not commit on main. Do not create another worktree merely to verify documentation.

`just planning-status` reports the private repository's status. `just planning-link` repairs its link. Planning commits require an explicit request and `just planning-commit` from the correct repository. Never stage the planning link/content in source. Push only when asked.

The old checkout at `/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp` and its worktrees are preserved. Do not modify, clean or delete them. Archived refs and the verified all-refs bundle keep the earlier implementation readable.

New source worktrees must build without planning or local skills. CI reads only tracked source inputs. Planning records stay in their owning repository and are not package data.
