# Template Generator

## ADDED Requirements

### Requirement: onetool MUST provide server creation command

Developers MUST be able to generate new backend servers from template with a single command.

#### Scenario: Developer creates new backend

**Given** developer wants to create onetool-finance backend
**When** they run `onetool server create onetool-finance --description "Financial tools" --category "Finance"`
**Then** new directory onetool-finance/ is created
**And** template files are copied from onetool-common/template/
**And** placeholders {name}, {package}, {description} are replaced
**And** module name is otfinance (following naming convention)
**And** git repository is initialized
**And** initial commit is created
**And** sync.py is run to get shared files
**And** `just check` is run to verify template validity

#### Scenario: Developer creates backend without git initialization

**Given** developer wants to manage git separately
**When** they run `onetool server create onetool-finance --skip-git`
**Then** template is generated successfully
**And** no git repository is initialized
**And** developer can set up git manually

#### Scenario: Developer creates backend without syncing

**Given** developer wants to customize before syncing
**When** they run `onetool server create onetool-finance --skip-sync`
**Then** template is generated successfully
**And** sync.py is not run
**And** developer can run sync.py manually later

### Requirement: Generated backend MUST follow naming conventions

Backend naming MUST follow the pattern: onetool-{category} for package, ot{category} for module.

#### Scenario: Checking naming conventions

**Given** backend is created with name onetool-finance
**When** developer inspects generated files
**Then** package name in pyproject.toml is onetool-finance
**And** module directory is src/otfinance/
**And** import statements use otfinance
**And** PyPI package name is one-finance

### Requirement: Template generator MUST show next steps

After generating backend, clear instructions MUST guide developer on what to do next.

#### Scenario: Backend generation completes

**Given** onetool-finance backend was just generated
**When** generation completes
**Then** output shows directory structure
**And** output shows commands to run: cd, add tools, just check, publish
**And** output suggests where to add tools (src/otfinance/tools/)
**And** developer knows exactly what to do next
