---
name: Quick Apply
description: Plan and apply small changes across code, tests, specs, docs, and config in one pass.
category: onetool
tags: [apply, quick, change, all-in-one]
---

## Purpose

Streamlined workflow for small-to-medium changes that don't warrant full OpenSpec proposal scaffolding. Combines planning, implementation, spec updates, doc sync, and config migration into a single pass.

**Use this for:**
- Bug fixes with clear scope
- Small features or enhancements
- Refactoring with known boundaries
- Config migrations
- Documentation updates with code changes

**Use OpenSpec proposal instead for:**
- Breaking changes
- New capabilities spanning multiple systems
- Architectural decisions needing design review
- Changes requiring stakeholder approval

---

## Input

This command accepts either:
1. **Direct instruction** - Describe the change in the conversation
2. **Markdown file** - Reference a file with change details (e.g., `plan/consult/some-fix.md`)

If input is unclear, ASK the user to clarify before proceeding.

---

## Guardrails

- Keep changes tightly scoped to the requested outcome
- Favor straightforward, minimal implementations
- Code is the source of truth - specs and docs follow implementation
- DO NOT create commits unless explicitly requested
- Present a plan before making changes
- ASK before proceeding to each major phase

---

## Step 1: Understand the Change

1. Read any referenced files or instructions
2. Explore relevant code with `rg` or file reads to understand current state
3. Identify all affected areas:
   - Source files to modify
   - Tests to add/update
   - Specs to update
   - Docs to sync
   - Config to migrate

---

## Step 2: Present the Plan

Show a concise plan:

```text
## Change: <one-line summary>

### Code Changes
- [ ] file.py: <what changes>

### Test Changes
- [ ] test_file.py: <what changes>

### Spec Updates
- [ ] openspec/specs/<spec>/spec.md: <what changes>

### Doc Updates
- [ ] docs/<file>.md: <what changes>
- [ ] README.md: <if affected>

### Config Changes
- [ ] <config file>: <what changes>
```

ASK: "Does this plan look correct? Reply 'yes' to proceed or suggest changes."

Wait for confirmation before proceeding.

---

## Step 3: Apply Code Changes

1. Make the code changes as planned
2. Keep edits minimal and focused
3. Run linting/type checks if configured
4. Report any issues encountered

---

## Step 4: Apply Test Changes

1. Add or update tests for the changed behavior
2. Follow project testing conventions (see `AGENTS.md`)
3. Ensure tests have proper markers (smoke/unit/integration, component tags)
4. Run affected tests to verify they pass

Report test results before proceeding.

---

## Step 5: Update Specs

If specs exist for the changed functionality:

1. Locate relevant specs in `openspec/specs/`
2. Update requirements to match new implementation
3. Update or add scenarios as needed
4. Run `openspec validate --strict` if available

Skip this step if no specs are affected.

---

## Step 6: Sync Documentation

Review and update affected docs:

### 6.1 README.md
- Update if features, usage, or examples changed

### 6.2 docs/ files
- Update relevant documentation pages
- Ensure code examples are accurate
- Update CLI flags or API signatures

### 6.3 docs/llms.txt
- Update if tool functions or CLI changed

### 6.4 Docstrings
- Ensure function docstrings match new behavior

---

## Step 7: Config Migration

If config changes are needed:

1. Update default config values
2. Add migration logic if breaking existing configs
3. Update config documentation
4. Test config loading with new values

---

## Step 8: OpenSpec spec check

Verify that any specs in `openspec/specs/` affected by your changes are accurate and complete. Code is the source of truth—specs must match the implementation.

## Step 9: Summary

Present a summary of all changes:

```text

## Summary of Applied Changes

### Code
- ✅ file.py: <summary>

### Tests
- ✅ test_file.py: <summary>
- Test results: X passed

### Specs
- ✅ spec.md: <summary>

### Docs
- ✅ README.md: <summary>

### Config
- ✅ config.yaml: <summary>

```
