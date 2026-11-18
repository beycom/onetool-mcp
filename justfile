# OneTool V4 development
set positional-arguments := true

default:
    @just --list --unsorted

install:
    uv sync --group dev

install-locked:
    uv sync --locked --group dev

check: lint typecheck test

lint:
    uv run ruff check src tests scripts
    uv run ruff format --check src tests scripts

typecheck:
    uv run mypy src scripts/release.py

test *args:
    uv run pytest {{ args }}

build:
    uv build
    cp scripts/install.sh dist/install.sh

# Create a new branch in a flat, fully bootstrapped WTP worktree
worktree-new branch base="main":
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v wtp >/dev/null 2>&1; then
        echo "wtp is required. Install it with: brew install satococoa/tap/wtp" >&2
        exit 127
    fi
    branch={{ quote(branch) }}
    base={{ quote(base) }}
    worktree_name="${branch##*/}"
    main_worktree="$(wtp cd @)"
    main_parent="$(cd "$(dirname "$main_worktree")" && pwd -P)"
    worktree_base="$main_parent/onetool-mcp-worktrees"
    flat_path="$worktree_base/$worktree_name"

    if [[ -z "$worktree_name" ]]; then
        echo "branch must end with a worktree name" >&2
        exit 2
    fi
    if [[ -e "$flat_path" || -L "$flat_path" ]]; then
        echo "worktree destination already exists: $flat_path" >&2
        exit 1
    fi

    worktree_path="$(wtp add -b "$branch" "$base" --quiet)"
    case "$worktree_path/" in
        "$worktree_base/"*) ;;
        *)
            echo "wtp created an unexpected path outside $worktree_base: $worktree_path" >&2
            exit 1
            ;;
    esac

    if [[ "$worktree_path" != "$flat_path" ]]; then
        old_parent="$(dirname "$worktree_path")"
        git worktree move "$worktree_path" "$flat_path"
        worktree_path="$flat_path"

        while [[ "$old_parent" != "$worktree_base" ]]; do
            rmdir "$old_parent" 2>/dev/null || break
            old_parent="$(dirname "$old_parent")"
        done
    fi

    # wtp reads .wtp.yml from the main checkout, which predates V4 until the
    # cutover merge, so make the shared links here as well. Existing links stay.
    for shared in planning .codex .mcp.json; do
        if [[ -e "$main_worktree/$shared" && ! -e "$worktree_path/$shared" && ! -L "$worktree_path/$shared" ]]; then
            ln -s "$main_worktree/$shared" "$worktree_path/$shared"
        fi
    done
    [[ -e "$worktree_path/.claude" || -L "$worktree_path/.claude" ]] || ln -s .codex "$worktree_path/.claude"

    (cd "$worktree_path" && just install-locked)
    printf 'Created worktree: %s\n' "$worktree_path"

# Link ../onetool-mcp-planning into planning/ and restore the .claude link
planning-link:
    #!/usr/bin/env bash
    set -euo pipefail
    common_dir="$(git rev-parse --path-format=absolute --git-common-dir)"
    repo="$(dirname "$common_dir")/../onetool-mcp-planning"
    if [[ ! -d "$repo/.git" ]]; then
        echo "planning repository missing at $repo; clone or create it beside this checkout" >&2
        exit 1
    fi
    if [[ -e planning && ! -L planning ]]; then
        echo "planning is a real directory, not a link; move it aside before linking" >&2
        exit 1
    fi
    if [[ ! -d planning ]]; then
        rm -f planning
        ln -s "$repo" planning
    fi
    if [[ ! -d .codex ]]; then
        echo "warning: .codex is missing; restore the agent configuration before creating worktrees" >&2
    fi
    [[ -e .claude || -L .claude ]] || ln -s .codex .claude
    ls -ld planning .claude
    if [[ -e .codex || -L .codex ]]; then ls -ld .codex; fi

# Uncommitted planning changes and the count of commits not yet on origin/main
planning-status:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -d planning/.git ]]; then
        echo "planning does not resolve; run: just planning-link" >&2
        exit 1
    fi
    git -C planning status --short
    if ! git -C planning rev-parse --verify -q HEAD >/dev/null; then
        echo "no planning commits yet"
    elif git -C planning rev-parse --verify -q origin/main >/dev/null; then
        echo "ahead of origin/main: $(git -C planning rev-list --count origin/main..HEAD)"
    else
        echo "ahead of origin/main: unknown (no origin/main)"
    fi

# Commit every planning change in the planning repository only. Never pushes.
planning-commit msg="":
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -d planning/.git ]]; then
        echo "planning does not resolve; run: just planning-link" >&2
        exit 1
    fi
    msg={{ quote(msg) }}
    git -C planning add -A
    if git -C planning diff --cached --quiet; then
        echo "nothing to commit in planning"
        exit 0
    fi
    if [[ -z "$msg" ]]; then
        count="$(git -C planning diff --cached --name-only | wc -l | tr -d " ")"
        msg="planning: $(date +%F) $count records"
    fi
    git -C planning commit -q -m "$msg"
    git -C planning log --oneline -1

# Set a V4 version locally. Review docs/changelog references before a candidate.
version value:
    uv run python scripts/release.py version {{ quote(value) }}

# Use the Python from a clean wheel installation for runtime-only license inventory.
release-inventory python=".venv/bin/python":
    {{ quote(python) }} scripts/release.py inventory dist
