---
name: Doc Sync
description: Check code and ensure documentation is in sync with implementation.
category: onetool
tags: [documentation, sync, review, tools, cli]
---

## Purpose

Verify that all documentation accurately reflects the current implementation by reviewing CLI commands and tools against their documentation.

## Scope
- README.md
- All docs in `/docs`
- `docs/llms.txt`

**Guardrails**
- DO NOT make changes without explicit user confirmation
- DO NOT create commits - this is a review command
- Present findings clearly in a table format
- Code is the source of truth - docs should match implementation

---

## Step 1: CLI Documentation Sync

Review each CLI command against its documentation.

### 1.1 onetool

Compare `src/onetool/` implementation with:
- `docs/reference/cli/onetool.md`
- README.md CLI section
- `docs/llms.txt` CLI section

Check for:
- Command line flags and options match implementation
- Default values are accurate
- Environment variables are documented
- Usage examples work correctly

### 1.2 bench

Compare `src/bench/` implementation with:
- `docs/reference/cli/bench.md`
- README.md CLI section (if mentioned)
- `docs/llms.txt` CLI section

Check for:
- Command line flags and options match implementation
- Default values are accurate
- Environment variables are documented
- Usage examples work correctly

### 1.3 Other CLIs

Check for any additional CLI entry points in `pyproject.toml` and verify they are documented.

---

## Step 2: Tool Documentation Sync

Review each tool namespace against its documentation.

For each tool in `src/ot_tools/`:

### 2.1 Read the Implementation

- Read the tool source file
- Note the `namespace` variable
- List all public functions with their signatures
- Extract docstrings and parameter descriptions
- Note default values and required parameters

### 2.2 Compare with Documentation

Compare against:
- `docs/reference/tools/<namespace>.md`
- `docs/llms.txt` tool listing
- README.md (if tool is mentioned in features/capabilities)

Check for:
- Function names match documentation
- Parameter names and types match
- Default values are accurate
- Docstrings align with documentation descriptions
- All public functions are documented
- No documented functions that don't exist in code

### 2.3 Tools to Review

Process each tool file in `src/ot_tools/`:

1. `brave_search.py` → `docs/reference/tools/brave-search.md`
2. `web_fetch.py` → `docs/reference/tools/web-fetch.md`
3. `context7.py` → `docs/reference/tools/context7.md`
4. `code_search.py` → `docs/reference/tools/code-search.md`
5. `transform.py` → `docs/reference/tools/transform.md`
6. `db.py` → `docs/reference/tools/database.md`
7. `package.py` → `docs/reference/tools/package.md`
8. `ripgrep.py` → `docs/reference/tools/ripgrep.md`
9. `excel.py` → `docs/reference/tools/excel.md`
10. `file.py` → `docs/reference/tools/file.md`
11. `diagram.py` → `docs/reference/tools/diagram.md`
12. `convert.py` → `docs/reference/tools/convert.md`
13. `grounding_search.py` → `docs/reference/tools/grounding-search.md`
14. `internal.py` → `docs/reference/tools/ot.md`

---

## Step 3: Cross-Document Consistency

### 3.1 README.md

Verify README accurately reflects:
- List of namespaces/tools matches actual tools
- Feature descriptions match implementation
- Installation instructions work
- Quick start examples are accurate
- Links to docs are valid

### 3.2 docs/llms.txt

Verify `docs/llms.txt` reflects:
- All namespaces are listed
- Function names for each namespace are accurate
- No missing or extra functions
- Quick invocation examples work

### 3.3 Index Pages

Check that index pages list all relevant items:
- `docs/reference/tools/index.md` lists all tool docs
- `docs/reference/cli/index.md` lists all CLI docs

---

## Step 4: Present Findings

After completing all reviews, present a consolidated findings table:

```text
| # | Area | Doc File | Issue Type | Description | Suggested Fix |
|---|------|----------|------------|-------------|---------------|
```

Issue Types:
- `missing` - Feature/function exists in code but not documented
- `outdated` - Documentation exists but doesn't match current implementation
- `incorrect` - Documentation contains wrong information
- `removed` - Documentation describes something that no longer exists
- `broken` - Examples or links that don't work

Group findings by:
1. CLI issues
2. Tool issues (grouped by namespace)
3. Cross-document issues

---

## Step 5: Apply Fixes

Present the numbered list and ASK: "Which issues would you like me to fix? (e.g., '1, 3, 5', 'all', 'none')"

Apply only the confirmed fixes, then show a summary of changes made.
