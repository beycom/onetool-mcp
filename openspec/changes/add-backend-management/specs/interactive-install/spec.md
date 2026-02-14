# Interactive Installation

## ADDED Requirements

### Requirement: onetool MUST provide interactive installation wizard

New users MUST have a guided installation experience for selecting and installing backends.

#### Scenario: New user runs installation wizard

**Given** user has just installed onetool-mcp
**When** user runs `onetool install`
**Then** wizard shows checkbox list of available backends
**And** each backend shows: name, description, category
**And** official backends listed: onetool-util, onetool-dev, onetool-xero
**And** external backends optionally listed: github, devtools
**And** user can select multiple backends with checkboxes

#### Scenario: User selects and installs backends

**Given** user is in installation wizard
**When** user selects onetool-util and onetool-dev
**Then** wizard calls backends.install() for each selected backend
**And** progress is shown for each installation
**And** errors are handled gracefully with clear messages
**And** default configs are created for each backend
**And** summary shows what was installed at the end

#### Scenario: Installation wizard updates Claude Code config

**Given** user has Claude Code installed
**When** wizard completes backend installation
**Then** wizard offers to update Claude Code mcp.json
**And** if user accepts, mcp.json is updated with backend configs
**And** user can start using backends in Claude Code immediately

### Requirement: Installation wizard MUST show quick start guide

After installation, users MUST know how to verify installation and use their first tool.

#### Scenario: Installation completes successfully

**Given** onetool-util and onetool-dev were installed
**When** installation wizard completes
**Then** output shows example commands to try
**And** output shows how to verify installation (onetool backends list)
**And** output shows first tool call to try (__ot file.read(path="README.md"))
**And** user has clear next steps
