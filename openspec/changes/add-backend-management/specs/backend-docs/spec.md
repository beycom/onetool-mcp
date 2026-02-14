# Backend Documentation

## ADDED Requirements

### Requirement: Migration guide MUST document v1.x to v2.0 changes

Users upgrading from v1.x MUST have clear documentation of breaking changes and migration steps.

#### Scenario: User migrating from v1.x

**Given** user has v1.x installed
**When** they read docs/migration-v2.md
**Then** they understand config file format changes
**And** they see what tools moved where (file → onetool-util, db → onetool-dev)
**And** they have step-by-step upgrade instructions
**And** troubleshooting section covers common issues

### Requirement: Backend development guide MUST enable creating new backends

Developers MUST be able to create new backend servers following documented patterns.

#### Scenario: Developer creates first backend

**Given** developer wants to create new backend
**When** they read docs/backend-development.md
**Then** they understand how to use onetool-common library
**And** they understand project structure requirements
**And** they see tool registration patterns with examples
**And** they know how to test backend servers
**And** they know how to publish to PyPI
**And** they have references to onetool-util, onetool-dev, onetool-xero as examples

### Requirement: Architecture overview MUST explain v2.0 design

Users and developers MUST understand the frontend/proxy vs backend architecture.

#### Scenario: Understanding v2.0 architecture

**Given** user reads docs/architecture-v2.md
**When** they want to understand the system
**Then** they see clear explanation of frontend vs backend servers
**And** they see proxy architecture diagram
**And** they understand token efficiency (2K vs 30-60K)
**And** they understand fault isolation benefits
**And** they understand dependency isolation benefits
**And** they understand code execution paradigm

### Requirement: Installation guide MUST cover all installation scenarios

New users MUST be able to install onetool-mcp and backends successfully.

#### Scenario: New user installing onetool

**Given** new user reads docs/installation.md
**When** they follow the guide
**Then** they know how to install onetool core
**And** they know how to install backends (interactive wizard and manual)
**And** they know how to configure backends
**And** they know how to set up Claude Code integration
**And** they have examples and quick start commands
**And** troubleshooting section covers common issues

### Requirement: Documentation MUST be discoverable

All documentation MUST be linked from main README and organized in docs/ directory.

#### Scenario: User looking for documentation

**Given** user reads README.md
**When** they look for documentation links
**Then** they see links to docs/installation.md, docs/migration-v2.md, etc.
**And** docs/index.md provides navigation to all docs
**And** CLAUDE.md references new architecture
**And** all documentation is up to date with v2.0
