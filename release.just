# Release Tasks for OneTool
# Usage: just release::<task>
#
# WORKFLOW:
#   1. just release::prep VERSION    - Bump version, generate changelog draft
#   2. Edit CHANGELOG.md             - Copy relevant parts from tmp/changelog-entry.md
#   3. just release::check           - Run all quality checks
#   4. just release::publish VERSION - Dry-run by default, --force to publish

set dotenv-load := true
set shell := ["zsh", "-c"]

default:
    @just --list --unsorted

# --------------------------------------------------------------------------
# Step 1: Prepare - bump version and generate changelog draft
# --------------------------------------------------------------------------
prep version:
    @echo "=== Step 1: Prepare release {{ version }} ==="
    just release::set-version {{ version }}
    @mkdir -p tmp
    @echo "## [{{ version }}] - $(date +%Y-%m-%d)" > tmp/changelog-entry.md
    @echo "" >> tmp/changelog-entry.md
    @git cliff --unreleased --strip header 2>/dev/null >> tmp/changelog-entry.md || (echo "### Changes" >> tmp/changelog-entry.md && echo "" >> tmp/changelog-entry.md && git log $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~20")..HEAD --oneline --no-merges | sed 's/^/- /' >> tmp/changelog-entry.md)
    @echo ""
    @echo "Generated changelog draft in tmp/changelog-entry.md"
    @echo "─────────────────────────────────────"
    @cat tmp/changelog-entry.md
    @echo "─────────────────────────────────────"
    @echo ""
    @echo "TODO: Copy relevant parts to CHANGELOG.md (after line 2)"
    @${EDITOR:-code} CHANGELOG.md tmp/changelog-entry.md
    @echo "Next: just release::check"

# --------------------------------------------------------------------------
# Step 2: Check - lint, typecheck, tests, secrets scan, docs build, sanity
# --------------------------------------------------------------------------
check:
    @echo "=== Step 2: Pre-release checks ==="
    just lint
    just typecheck
    just test-all
    just secrets-check
    just docs-sync
    uv run mkdocs build --strict
    codex "/p-test-explore sanity.md retest all"
    @echo "=== All checks passed. Next: just release::publish VERSION ==="

# --------------------------------------------------------------------------
# Step 3: Publish - build, PyPI, GitHub, MCP Registry, docs
# Dry-run by default. Use --force to actually publish.
# --------------------------------------------------------------------------
publish version *args:
    uv run scripts/release_publish.py {{ version }} {{ args }}

# ============================================================================
# INDIVIDUAL PUBLISH STEPS (escape hatches)
# ============================================================================

# Set version in pyproject.toml, server.json, and package workspaces
set-version version:
    @echo "Setting version to {{ version }}"
    sed -i '' 's/^version = ".*"/version = "{{ version }}"/' pyproject.toml
    sed -i '' 's/"version": ".*"/"version": "{{ version }}"/g' server.json
    sed -i '' 's/^version = ".*"/version = "{{ version }}"/' packages/onetool-pack/pyproject.toml
    @echo "Updated pyproject.toml, server.json, and package pyprojects."

# Build package
build:
    rm -rf dist/ build/ *.egg-info
    uv build

# Publish to PyPI
pypi:
    uv publish

# Publish to MCP Registry
mcp:
    @mcp-publisher login github
    @mcp-publisher publish

# Deploy docs to GitHub Pages
docs:
    uv run mkdocs gh-deploy --force

# Commit, tag, and push
tag version:
    git add -A
    git commit -m "Release {{ version }}" || true
    git tag -a "v{{ version }}" -m "Release {{ version }}"
    git push origin main
    git push origin "v{{ version }}"

# Create GitHub release (extracts notes from CHANGELOG.md)
gh-release version:
    uv run python -c "from scripts.release_publish import extract_release_notes; n=extract_release_notes('{{ version }}'); open('tmp/release-notes.md','w').write(n) if n else None"
    gh release create "v{{ version }}" --title "v{{ version }}" --notes-file tmp/release-notes.md || gh release create "v{{ version }}" --title "v{{ version }}" --generate-notes

# Delete a release (GitHub release + local/remote tags)
delete-release version:
    gh release delete "v{{ version }}" --yes || true
    git push origin --delete "v{{ version }}" || true
    git tag -d "v{{ version }}" || true
    @echo "Deleted release v{{ version }}"
