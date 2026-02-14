# DRY Infrastructure

## ADDED Requirements

### Requirement: Common files MUST be centralized in onetool-common/shared/

Development practices, OpenSpec docs, quality configs, and build scripts MUST exist in a single source of truth to eliminate duplication.

#### Scenario: Developer updates a practice guide

**Given** a practice guide needs updating (e.g., git.md)
**When** developer edits onetool-common/shared/dev/practices/git.md
**Then** the change can be synced to all backend projects
**And** only one file needs to be maintained

#### Scenario: New backend needs practice guides

**Given** a new backend server is created
**When** sync.py is run from the new backend directory
**Then** all 11 practice guides are copied from onetool-common/shared/dev/practices/
**And** developer doesn't need to manually copy files

### Requirement: Shared directory MUST include manifest describing sync rules

A manifest.yaml file MUST define what files are shared, where they sync to, and include descriptions for each sync rule.

#### Scenario: Developer checks what files are synced

**Given** a developer wants to understand the sync system
**When** they read onetool-common/shared/manifest.yaml
**Then** they see all sync rules with source, destination, and description
**And** they understand which files will be synced to their project

### Requirement: Common justfile recipes MUST be importable

Standard build/test/lint recipes MUST be defined once in common.just and imported by all backend projects.

#### Scenario: Developer runs standard checks

**Given** a backend project imports common.just
**When** developer runs `just check`
**Then** standard recipes (lint, test, fmt, typecheck) execute
**And** project-specific justfile can override or extend recipes as needed

#### Scenario: Common recipe is updated

**Given** a bug is fixed in common.just test recipe
**When** all backend projects import the updated common.just
**Then** all projects get the fix automatically
**And** no manual updates needed per project
