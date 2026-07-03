# _nf-docs Specification

## Purpose

Defines product-level documentation requirements for OneTool users. These
requirements cover discoverability, accuracy, and disclosure for public
documentation that users rely on when installing, configuring, invoking,
extending, and operating OneTool.

## Requirements

### Requirement: User Onboarding Documentation

OneTool SHALL provide user-facing onboarding documentation that enables a new
user to install OneTool, configure a client, and make a first tool call.

#### Scenario: Quick start path
- **GIVEN** a new user reading public documentation
- **WHEN** they follow the quick start
- **THEN** they SHALL find installation instructions
- **AND** a minimal MCP client configuration
- **AND** a first successful `run(command=...)` or `__onetool` invocation example

#### Scenario: Configuration entry point
- **GIVEN** a user configuring OneTool
- **WHEN** they read public configuration documentation
- **THEN** they SHALL find the current `onetool.yaml` sections and command-line config options
- **AND** the documented behavior SHALL match the current configuration specs

### Requirement: Public CLI Reference

OneTool SHALL document user-facing CLI commands, options, outputs, and failure
modes.

#### Scenario: Runtime command reference
- **GIVEN** a user needs to start OneTool
- **WHEN** they read CLI reference documentation
- **THEN** they SHALL find `onetool serve` options for stdio and HTTP runtime modes
- **AND** direct execution commands SHALL be documented separately from root MCP runtime commands

#### Scenario: Knowledge-base command reference
- **GIVEN** a user operates knowledge bases through the CLI
- **WHEN** they read CLI reference documentation
- **THEN** they SHALL find the supported `onetool kb` commands and their required arguments

### Requirement: Tool Reference Accuracy

OneTool SHALL provide public reference documentation for bundled tool packs that
matches the current runtime interface.

#### Scenario: Tool pack index
- **GIVEN** a user browsing tool documentation
- **WHEN** they open the tool reference index
- **THEN** they SHALL find all bundled packs grouped by availability or extra
- **AND** each pack entry SHALL identify its public tool functions

#### Scenario: Individual tool documentation
- **GIVEN** a user reads an individual tool pack page
- **WHEN** the page describes callable functions
- **THEN** signatures, required parameters, output shapes, dependencies, and examples SHALL match the current runtime interface

#### Scenario: Missing dependency disclosure
- **GIVEN** a tool requires an API key, optional package, external service, or browser
- **WHEN** the user reads that tool's reference page
- **THEN** the requirement SHALL be disclosed before examples that depend on it

### Requirement: Security And Privacy Disclosure

OneTool SHALL document security and privacy behavior that affects user trust,
local data, network calls, and telemetry.

#### Scenario: Security model documented
- **GIVEN** a user evaluating OneTool security
- **WHEN** they read public security documentation
- **THEN** they SHALL find the code validation, path boundary, secret handling, and proxy trust boundaries that apply at runtime

#### Scenario: Telemetry disclosure
- **GIVEN** anonymous telemetry is enabled by default
- **WHEN** a user reads public documentation or README material
- **THEN** the telemetry event contents and opt-out mechanisms SHALL be disclosed

### Requirement: Extension Documentation

OneTool SHALL document the supported user-facing extension workflow for adding
custom tools.

#### Scenario: Extension workflow
- **GIVEN** a user wants to add a custom tool
- **WHEN** they read extension documentation
- **THEN** they SHALL find the supported file placement, pack declaration, callable function shape, configuration, and reload workflow

#### Scenario: Third-party tool usage
- **GIVEN** a user wants to use a tool from another local project
- **WHEN** they read extension documentation
- **THEN** they SHALL find how to point `tools_dir` at that tool source
- **AND** how secrets or API keys are supplied for that tool

### Requirement: Documentation Consistency

Public documentation SHALL not advertise commands, config keys, tool names, or
runtime modes that are absent from the current product.

#### Scenario: Removed or unsupported surface omitted
- **GIVEN** a CLI command, config key, or tool function is not part of the current product
- **WHEN** public documentation is rendered or published
- **THEN** it SHALL NOT be presented as supported behavior

#### Scenario: Examples use real supported surfaces
- **GIVEN** public examples in docs or README material
- **WHEN** a user copies an example into a correctly configured OneTool environment
- **THEN** the example SHALL target real commands, packs, functions, and parameters
