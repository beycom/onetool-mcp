# Backend CLI

## ADDED Requirements

### Requirement: onetool MUST provide backend listing command

Users MUST be able to see all installed backends with their status and tool counts.

#### Scenario: User checks installed backends

**Given** onetool-util and onetool-dev are installed
**When** user runs `onetool backends list`
**Then** output shows table with: name, version, status, tool count
**And** status shows [running], [stopped], or [not installed]
**And** tool count shows number of tools provided by each backend

#### Scenario: User checks backends in JSON format

**Given** user wants machine-readable output
**When** user runs `onetool backends list --json`
**Then** output is valid JSON array
**And** each backend has: name, version, status, tool_count fields

### Requirement: onetool MUST provide backend installation command

Users MUST be able to install and register backends with a single command.

#### Scenario: User installs a new backend

**Given** onetool-util is not installed
**When** user runs `onetool backends install onetool-util`
**Then** uvx installs the package
**And** default config file is created in ~/.onetool/util.yaml
**And** backend is added to backend_servers in ~/.onetool/onetool.yaml
**And** installation is verified by starting backend
**And** success message shows backend is ready

#### Scenario: Installation fails due to package not found

**Given** user tries to install non-existent package
**When** user runs `onetool backends install fake-backend`
**Then** clear error message shows package not found
**And** no partial config files are created
**And** command exits with non-zero status

### Requirement: onetool MUST provide backend update command

Users MUST be able to check for and apply updates to backends.

#### Scenario: User updates all backends

**Given** multiple backends are installed
**When** user runs `onetool backends update`
**Then** each backend is checked for updates
**And** available updates are shown (old version → new version)
**And** updated backends are restarted
**And** summary shows what was updated

#### Scenario: User updates specific backend

**Given** onetool-util has an update available
**When** user runs `onetool backends update onetool-util`
**Then** only onetool-util is updated
**And** other backends are not checked or restarted

### Requirement: onetool MUST provide backend health check command

Users MUST be able to verify all backends are responding correctly.

#### Scenario: User checks backend health

**Given** multiple backends are configured
**When** user runs `onetool backends health`
**Then** each backend is started if not running
**And** backend.list_tools() is called to verify response
**And** response time is measured
**And** output shows: ✓ healthy, ⚠ warning (slow), or ✗ error
**And** tool count is reported for each backend

#### Scenario: Backend health check detects failure

**Given** a backend is misconfigured
**When** user runs `onetool backends health`
**Then** failed backend shows ✗ error with reason
**And** other backends still show their status
**And** command exits with non-zero if any backend failed

### Requirement: onetool MUST provide backend uninstall command

Users MUST be able to cleanly remove backends.

#### Scenario: User uninstalls a backend

**Given** onetool-util is installed
**When** user runs `onetool backends uninstall onetool-util`
**Then** user is prompted for confirmation
**And** after confirming, backend is stopped if running
**And** backend is removed from backend_servers config
**And** config file ~/.onetool/util.yaml is deleted
**And** uvx uninstalls the package
**And** success message confirms removal

#### Scenario: User forces uninstall without confirmation

**Given** user wants to skip confirmation
**When** user runs `onetool backends uninstall onetool-util --yes`
**Then** no confirmation prompt is shown
**And** backend is uninstalled immediately
