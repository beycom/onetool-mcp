# metadata-standardization Specification

## Purpose
TBD - created by archiving change standardize-backends. Update Purpose after archive.
## Requirements
### Requirement: All backend projects MUST use consistent license

All OneTool projects (onetool-mcp, onetool-common, onetool-util, onetool-dev, onetool-xero) MUST use GPL-3.0 license to ensure legal consistency.

#### Scenario: Developer checks license across projects

**Given** a developer working across multiple OneTool repositories
**When** they check the LICENSE file and pyproject.toml license field
**Then** all projects show GPL-3.0 as the license
**And** pyproject.toml classifiers include "License :: OSI Approved :: GNU General Public License v3 (GPLv3)"

### Requirement: All backend projects MUST use consistent author information

All projects MUST list "Gavin Las <beycom99@gmail.com>" as the author for consistency and contact purposes.

#### Scenario: Package maintainer needs to contact author

**Given** a user or contributor needs to contact the project author
**When** they check pyproject.toml authors field
**Then** they find "Gavin Las <beycom99@gmail.com>" in all projects

### Requirement: All backend projects MUST require Python 3.12+

All projects MUST require Python 3.12 or higher to align with onetool-mcp's requirements and ensure modern Python features are available.

#### Scenario: Developer sets up development environment

**Given** a developer setting up a new backend project
**When** they check pyproject.toml requires-python field
**Then** it shows ">=3.12"
**And** .python-version file contains "3.12"
**And** pyproject.toml classifiers list Python 3.12 and 3.13

### Requirement: Template placeholders MUST be replaced in generated backends

Server configuration files MUST NOT contain template placeholders like {package}, {name}, {description}.

#### Scenario: Generated backend has valid server.json

**Given** a backend server generated from template
**When** the server.json file is inspected
**Then** it contains actual values for package, name, and description
**And** no curly brace placeholders remain

