# onetool-cli Specification Delta

## MODIFIED Requirements

### Requirement: Init Validate

The CLI SHALL validate the OneTool configuration and report issues.

#### Scenario: Show configuration summary
- **WHEN** a user runs `ot-serve init validate`
- **THEN** the CLI displays configuration file location
- **AND** displays enabled tools and packs
- **AND** displays configured secrets (names only)

#### Scenario: Show dependency status
- **WHEN** a user runs `ot-serve init validate`
- **THEN** the CLI displays tool dependency status
- **AND** shows which CLI tools are installed or missing
- **AND** shows which Python libraries are available or missing

#### Scenario: Warn on missing dependencies
- **WHEN** a tool declares a CLI dependency that is not installed
- **THEN** the CLI displays a warning with the missing dependency name
- **AND** suggests how to install it if known
