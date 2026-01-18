# OpenSpec Technical Specification

> Comprehensive reference for OpenSpec - a spec-driven development framework for AI coding assistants.

## Overview

OpenSpec is a specification-driven development system that helps AI assistants understand project requirements, track changes through a formal proposal process, and maintain consistency between specifications and implementations.

### Core Concepts

| Concept | Description |
|---------|-------------|
| **Spec** | A requirements document describing a capability (what IS built) |
| **Change** | A proposal for modifying the system (what SHOULD change) |
| **Delta** | The difference between current and proposed requirements |
| **Archive** | Completed changes with their full history |

## File Structure

### Directory Layout

```
project-root/
├── AGENTS.md                    # Universal AI instructions (managed block)
├── CLAUDE.md                    # Claude-specific instructions (optional)
├── .claude/commands/openspec/   # Claude slash commands (optional)
│   ├── proposal.md
│   ├── apply.md
│   └── archive.md
└── openspec/
    ├── AGENTS.md                # Detailed OpenSpec workflow instructions
    ├── project.md               # Project context and conventions
    ├── specs/                   # Current truth - what IS built
    │   └── [capability]/
    │       ├── spec.md          # Requirements and scenarios
    │       └── design.md        # Technical patterns (optional)
    ├── changes/                 # Active proposals - what SHOULD change
    │   └── [change-id]/
    │       ├── proposal.md      # Why, what, impact
    │       ├── tasks.md         # Implementation checklist
    │       ├── design.md        # Technical decisions (optional)
    │       └── specs/           # Delta changes
    │           └── [capability]/
    │               └── spec.md  # ADDED/MODIFIED/REMOVED
    └── changes/archive/         # Completed changes
        └── YYYY-MM-DD-[change-id]/
```

### Files Created by `openspec init`

| File | Location | Purpose | Created When |
|------|----------|---------|--------------|
| `AGENTS.md` | project root | Universal AI agent instructions | Always |
| `CLAUDE.md` | project root | Claude-specific instructions | `--as claude` |
| `openspec/AGENTS.md` | openspec dir | Detailed workflow instructions | Always |
| `openspec/project.md` | openspec dir | Project context template | Always |
| `.claude/commands/openspec/*.md` | .claude dir | Slash commands | `--as claude` |

## Root Instruction Files

### Managed Block Pattern

Root files (`AGENTS.md`, `CLAUDE.md`) use a managed block pattern that allows:
- User content to be preserved outside the managed block
- OpenSpec instructions to be updated without losing customizations

```markdown
<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->
```

### Update Behavior

When `openspec update` runs on an existing file:

1. **Both markers found**: Replace content between markers, preserve everything else
2. **No markers found**: Prepend managed block to existing content
3. **One marker found**: Error (invalid state)
4. **File doesn't exist**: Create new file with managed block

This ensures user customizations (project context, code style guidelines) are never lost.

## Spec Files (`specs/[capability]/spec.md`)

### Structure

```markdown
# [Capability] Specification

## Purpose
[1-3 sentences describing what this capability does]

## Requirements

### Requirement: [Name]
The system SHALL [normative statement with SHALL/MUST].

#### Scenario: [Success case]
- **WHEN** [precondition]
- **THEN** [expected outcome]

#### Scenario: [Edge case]
- **GIVEN** [context]
- **WHEN** [action]
- **THEN** [result]
```

### Rules

| Rule | Description |
|------|-------------|
| Normative language | Use SHALL/MUST for requirements (not should/may) |
| Scenario format | Use `#### Scenario:` (4 hashtags) - not bullets, not bold |
| Minimum scenarios | Every requirement MUST have at least one scenario |
| Single capability | Each spec focuses on one coherent capability |

## Change Proposals (`changes/[change-id]/`)

### Required Files

| File | Purpose | Required |
|------|---------|----------|
| `proposal.md` | Why and what changes | Yes |
| `tasks.md` | Implementation checklist | Yes |
| `design.md` | Technical decisions | If complex |
| `specs/*/spec.md` | Delta requirements | Yes (at least one) |

### proposal.md Structure

```markdown
# Change: [Brief description]

## Why
[1-2 sentences on problem/opportunity]

## What Changes
- [Bullet list of changes]
- [Mark breaking changes with **BREAKING**]

## Impact
- Affected specs: [list capabilities]
- Affected code: [key files/systems]
```

### tasks.md Structure

```markdown
## 1. Implementation
- [ ] 1.1 Create database schema
- [ ] 1.2 Implement API endpoint
- [ ] 1.3 Add frontend component
- [ ] 1.4 Write tests
```

### design.md Structure (When Needed)

Create `design.md` when:
- Cross-cutting change (multiple services/modules)
- New architectural pattern
- New external dependency
- Security, performance, or migration complexity

```markdown
## Context
[Background, constraints, stakeholders]

## Goals / Non-Goals
- Goals: [...]
- Non-Goals: [...]

## Decisions
- Decision: [What and why]
- Alternatives considered: [Options + rationale]

## Risks / Trade-offs
- [Risk] → Mitigation

## Migration Plan
[Steps, rollback]
```

## Delta Operations

Delta specs define changes to requirements. They live in `changes/[change-id]/specs/[capability]/spec.md`.

### Operation Types

| Operation | Purpose | Format |
|-----------|---------|--------|
| `## ADDED Requirements` | New capabilities | Full requirement block |
| `## MODIFIED Requirements` | Changed behavior | Complete updated requirement |
| `## REMOVED Requirements` | Deprecated features | Name + reason |
| `## RENAMED Requirements` | Name changes | FROM/TO pairs |

### ADDED Requirements

```markdown
## ADDED Requirements

### Requirement: Two-Factor Authentication
Users MUST provide a second factor during login.

#### Scenario: OTP required
- **WHEN** valid credentials are provided
- **THEN** an OTP challenge is required
```

### MODIFIED Requirements

**Critical**: Include the COMPLETE modified requirement, not just changes.

```markdown
## MODIFIED Requirements

### Requirement: User Authentication
Users MUST authenticate using email and password with optional two-factor.

#### Scenario: Standard login
- **WHEN** valid credentials provided
- **THEN** return JWT token

#### Scenario: Two-factor enabled
- **WHEN** 2FA is enabled
- **THEN** require OTP after password
```

### REMOVED Requirements

```markdown
## REMOVED Requirements

### Requirement: Legacy Login
**Reason**: Replaced by User Authentication
**Migration**: Update all /legacy-login calls to /login
```

### RENAMED Requirements

```markdown
## RENAMED Requirements

- FROM: `### Requirement: Login`
- TO: `### Requirement: User Authentication`
```

### Cross-Section Rules

| Conflict | Result |
|----------|--------|
| Same requirement in MODIFIED and REMOVED | Error |
| Same requirement in ADDED and MODIFIED | Error |
| Same requirement in ADDED and REMOVED | Error |
| MODIFIED references old RENAMED name | Error (use new name) |
| RENAMED TO collides with ADDED | Error |

## Three-Stage Workflow

### Stage 1: Creating Changes (Proposal)

```
New request?
├─ Bug fix restoring spec behavior? → Fix directly
├─ Typo/format/comment? → Fix directly
├─ New feature/capability? → Create proposal
├─ Breaking change? → Create proposal
├─ Architecture change? → Create proposal
└─ Unclear? → Create proposal (safer)
```

**Steps:**
1. Review `openspec/project.md` and existing specs/changes
2. Choose unique verb-led `change-id` (e.g., `add-two-factor-auth`)
3. Scaffold proposal.md, tasks.md, optional design.md
4. Draft spec deltas with ADDED/MODIFIED/REMOVED
5. Validate with `openspec validate <id> --strict`
6. **Wait for approval before implementing**

### Stage 2: Implementing Changes (Apply)

**Steps:**
1. Read proposal.md, design.md (if exists), tasks.md
2. Implement tasks sequentially
3. Confirm completion before updating statuses
4. Mark all tasks as `- [x]` when done

### Stage 3: Archiving Changes

**Steps:**
1. Run `openspec archive <change-id> --yes`
2. Changes move to `archive/YYYY-MM-DD-[change-id]/`
3. Delta specs merge into main `specs/` directory
4. Validate with `openspec validate --strict`

## Archive Process Details

When archiving, the system:

1. **Validates** the change (unless `--no-validate`)
2. **Checks task completion** (warns if incomplete)
3. **Applies spec updates** (unless `--skip-specs`):
   - ADDED: Appends new requirements
   - MODIFIED: Replaces existing requirements (full content)
   - REMOVED: Deletes requirements
   - RENAMED: Updates requirement names, preserves content
4. **Moves** change directory to archive with date prefix

### Archive Behavior for New Specs

| Operation | Existing Spec | New Spec |
|-----------|---------------|----------|
| ADDED | Append | Create skeleton + append |
| MODIFIED | Replace | Error (no spec to modify) |
| REMOVED | Delete | Warning (nothing to remove) |
| RENAMED | Update name | Error (no spec to rename) |

## Validation

### Validation Levels

| Level | Description | Blocks Archive |
|-------|-------------|----------------|
| ERROR | Critical issues | Yes |
| WARNING | Potential problems | No (Yes with `--strict`) |
| INFO | Suggestions | No |

### Common Validation Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "Change must have at least one delta" | No specs/ directory or no operation headers | Add `## ADDED Requirements` etc. |
| "Requirement must have at least one scenario" | Missing `#### Scenario:` | Add scenario with WHEN/THEN |
| "must contain SHALL or MUST" | Missing normative language | Use "SHALL" or "MUST" in requirement |
| "Duplicate requirement" | Same name in same section | Remove duplicate |
| "present in multiple sections" | Conflicting operations | Keep only one operation |

### Scenario Format Errors

**Correct:**
```markdown
#### Scenario: User login success
- **WHEN** valid credentials provided
- **THEN** return JWT token
```

**Wrong:**
```markdown
- **Scenario: User login**  ❌ (bullet point)
**Scenario**: User login     ❌ (bold, no header)
### Scenario: User login     ❌ (wrong header level)
```

## CLI Commands

### Core Commands

```bash
# Initialize OpenSpec
openspec init [path]              # Initialize in path or current directory
openspec init --as claude         # Target Claude Code
openspec init --as opencode       # Target OpenCode
openspec init --skip-pkg          # Skip slash command provisioning

# List items
openspec list                     # List active changes
openspec list --specs             # List specifications
openspec list --json              # Machine-readable output

# Show details
openspec show [item]              # Display change or spec
openspec show [item] --json       # JSON output
openspec show [change] --json --deltas-only

# Validate
openspec validate [item]          # Validate change or spec
openspec validate [item] --strict # Comprehensive validation

# Archive
openspec archive <change-id>      # Interactive archive
openspec archive <change-id> --yes  # Non-interactive
openspec archive <change-id> --skip-specs  # Skip spec updates

# Update instructions
openspec update [path]            # Refresh instruction files
```

### Command Flags

| Flag | Description |
|------|-------------|
| `--json` | Machine-readable output |
| `--type change\|spec` | Disambiguate items |
| `--strict` | Comprehensive validation |
| `--skip-specs` | Archive without spec updates |
| `--yes` / `-y` | Skip confirmation prompts |
| `--force` / `-f` | Overwrite existing files |

## AI Tool Configuration

### Supported Tools

| Tool | Root File | Slash Commands | Directory |
|------|-----------|----------------|-----------|
| Claude Code | CLAUDE.md | proposal, apply, archive | .claude/commands/openspec/ |
| OpenCode | - | proposal, apply, archive | .opencode/prompts/ |
| Cursor | - | proposal, apply, archive | .cursor/prompts/ |
| Windsurf | - | proposal, apply, archive | .windsurfprompts/ |
| Cline | CLINE.md | proposal, apply, archive | .cline/prompts/ |

### Slash Command Structure

Each slash command has:
- **Frontmatter**: Name, description, category, tags
- **Guardrails**: Behavior constraints
- **Steps**: Ordered workflow
- **References**: CLI commands for context

Example (`.claude/commands/openspec/proposal.md`):
```markdown
---
name: OpenSpec: Proposal
description: Scaffold a new OpenSpec change and validate strictly.
category: OpenSpec
tags: [openspec, change]
---

**Guardrails**
- Favor straightforward, minimal implementations first
- Do not write code during proposal stage

**Steps**
1. Review openspec/project.md and existing specs
2. Choose unique change-id and scaffold files
...

**Reference**
- Use `openspec show <id> --json --deltas-only` for details
```

## Best Practices

### Change ID Naming

- Use kebab-case: `add-user-auth`, `fix-login-bug`
- Verb-led prefixes: `add-`, `update-`, `remove-`, `refactor-`
- Keep short and descriptive
- Ensure uniqueness (append `-2`, `-3` if taken)

### Capability Naming

- Use verb-noun: `user-auth`, `payment-capture`
- Single purpose per capability
- 10-minute understandability rule
- Split if description needs "AND"

### Simplicity Guidelines

- Default to <100 lines of new code
- Single-file implementations until proven insufficient
- Avoid frameworks without clear justification
- Choose boring, proven patterns

### Complexity Triggers

Only add complexity with:
- Performance data showing current solution too slow
- Concrete scale requirements (>1000 users, >100MB data)
- Multiple proven use cases requiring abstraction

## Error Recovery

### Common Issues

| Issue | Solution |
|-------|----------|
| Change conflicts | Run `openspec list`, check overlapping specs, coordinate |
| Validation failures | Run with `--strict`, check JSON output, fix format |
| Missing context | Read project.md, check related specs, ask for clarification |
| Archive fails | Fix validation errors, complete tasks, retry |

### Debugging Commands

```bash
# Check delta parsing
openspec show [change] --json --deltas-only

# Validate comprehensively
openspec validate [item] --strict

# Inspect specific requirement
openspec show [spec] --json -r 1

# Full-text search
rg -n "Requirement:|Scenario:" openspec/specs
```

## Implementation Notes

### Marker-Based Updates

The `updateFileWithMarkers` function:

```python
def update_file_with_markers(path, content, start_marker, end_marker):
    if file_exists(path):
        existing = read_file(path)
        start_idx = find_marker(existing, start_marker)
        end_idx = find_marker(existing, end_marker)

        if start_idx != -1 and end_idx != -1:
            # Replace between markers
            return before + start_marker + content + end_marker + after
        elif start_idx == -1 and end_idx == -1:
            # Prepend to existing content
            return start_marker + content + end_marker + "\n\n" + existing
        else:
            raise Error("Invalid marker state")
    else:
        # Create new file
        return start_marker + content + end_marker
```

### Delta Application Order

When archiving, operations apply in this order:
1. RENAMED (update references first)
2. REMOVED (delete obsolete)
3. MODIFIED (update existing)
4. ADDED (append new)

This order prevents conflicts and maintains referential integrity.

## Quick Reference

### File Purposes

| File | Purpose |
|------|---------|
| `proposal.md` | Why and what (business case) |
| `tasks.md` | Implementation steps (checklist) |
| `design.md` | Technical decisions (architecture) |
| `spec.md` | Requirements and behavior (contract) |

### Stage Indicators

| Location | Meaning |
|----------|---------|
| `changes/` | Proposed, not yet built |
| `specs/` | Built and deployed |
| `archive/` | Completed changes |

### CLI Essentials

```bash
openspec list              # What's in progress?
openspec show [item]       # View details
openspec validate --strict # Is it correct?
openspec archive <id> -y   # Mark complete
```

---

*Based on OpenSpec by Fission-AI. See [original implementation](https://github.com/Fission-AI/OpenSpec) for reference.*
