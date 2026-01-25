# tool-package Specification

## Purpose

Check latest versions for npm, PyPI packages and search OpenRouter AI models. No API keys required.
## Requirements
### Requirement: npm Version Check

The `npm()` function SHALL check latest versions for npm packages.

#### Scenario: Single package
- **GIVEN** a package name
- **WHEN** `npm(packages=["react"])` is called
- **THEN** it SHALL return YAML flow style with the package name and latest version

#### Scenario: Multiple packages
- **GIVEN** multiple package names
- **WHEN** `npm(packages=["react", "lodash"])` is called
- **THEN** it SHALL return versions for all packages

#### Scenario: Unknown package
- **GIVEN** a non-existent package name
- **WHEN** `npm(packages=["nonexistent-pkg-xyz"])` is called
- **THEN** it SHALL return "unknown" as the version

### Requirement: PyPI Version Check

The `pypi()` function SHALL check latest versions for Python packages.

#### Scenario: Single package
- **GIVEN** a package name
- **WHEN** `pypi(packages=["requests"])` is called
- **THEN** it SHALL return a list with the package name and latest version

#### Scenario: Multiple packages
- **GIVEN** multiple package names
- **WHEN** `pypi(packages=["requests", "flask"])` is called
- **THEN** it SHALL return versions for all packages

#### Scenario: Unknown package
- **GIVEN** a non-existent package name
- **WHEN** `pypi(packages=["nonexistent-pkg-xyz"])` is called
- **THEN** it SHALL return "unknown" as the version

### Requirement: AI Model Search

The `models()` function SHALL search OpenRouter models.

#### Scenario: Search by name
- **GIVEN** a search query
- **WHEN** `models(query="claude")` is called
- **THEN** it SHALL return matching models with id, name, context_length, and pricing

#### Scenario: Filter by provider
- **GIVEN** a provider filter
- **WHEN** `models(provider="anthropic")` is called
- **THEN** it SHALL return only models from that provider

#### Scenario: List all models
- **GIVEN** no filters
- **WHEN** `models()` is called
- **THEN** it SHALL return all available models (up to limit)

### Requirement: Unified Version Check

The `version()` function SHALL check latest versions for packages from any supported registry.

#### Scenario: npm packages
- **GIVEN** registry="npm" and a list of package names
- **WHEN** `version(registry="npm", packages=["react", "lodash"])` is called
- **THEN** it SHALL return versions for all packages with parallel fetching

#### Scenario: PyPI packages
- **GIVEN** registry="pypi" and a list of package names
- **WHEN** `version(registry="pypi", packages=["requests", "flask"])` is called
- **THEN** it SHALL return versions for all packages with parallel fetching

#### Scenario: OpenRouter models
- **GIVEN** registry="openrouter" and model queries
- **WHEN** `version(registry="openrouter", packages=["claude", "gpt-4"])` is called
- **THEN** it SHALL return matching models with id, name, and pricing

#### Scenario: Current version comparison
- **GIVEN** a dict mapping package names to current versions
- **WHEN** `version(registry="npm", packages={"react": "^18.0.0"})` is called
- **THEN** it SHALL return both current and latest versions for comparison

### Requirement: Package Tool Logging

The package tools SHALL log all operations using LogSpan.

#### Scenario: version logging
- **GIVEN** a version check via `npm()`, `pypi()`, or `version()`
- **WHEN** the operation completes
- **THEN** it SHALL log span="package.version" with registry and count

#### Scenario: models logging
- **GIVEN** a models search
- **WHEN** `models(query="claude")` completes
- **THEN** it SHALL log span="package.models" with query

### Requirement: Dependency Audit

The `audit()` function SHALL audit project dependencies against latest registry versions.

#### Scenario: Auto-detect Python project
- **GIVEN** a directory containing pyproject.toml
- **WHEN** `audit()` is called without arguments
- **THEN** it SHALL detect the manifest, extract dependencies, fetch latest versions from PyPI, and return a structured comparison

#### Scenario: Auto-detect npm project
- **GIVEN** a directory containing package.json
- **WHEN** `audit()` is called without arguments
- **THEN** it SHALL detect the manifest, extract dependencies, fetch latest versions from npm, and return a structured comparison

#### Scenario: Explicit registry
- **GIVEN** a project with multiple manifest files
- **WHEN** `audit(registry="npm")` is called
- **THEN** it SHALL use the npm registry and package.json manifest

#### Scenario: Custom path
- **GIVEN** a subdirectory with its own manifest
- **WHEN** `audit(path="./frontend")` is called
- **THEN** it SHALL audit dependencies from that path's manifest

#### Scenario: Status classification
- **GIVEN** a dependency audit result
- **WHEN** versions are compared
- **THEN** each package SHALL have a status of "current", "update_available", "major_update", or "unknown"

#### Scenario: Return structure
- **GIVEN** a successful audit
- **WHEN** the function returns
- **THEN** it SHALL include: manifest path, registry, packages list with (name, required, latest, status), and summary counts

#### Scenario: Missing manifest
- **GIVEN** a directory with no recognized manifest file
- **WHEN** `audit()` is called
- **THEN** it SHALL return an error message indicating no manifest found

#### Scenario: pyproject.toml sections
- **GIVEN** pyproject.toml with dependencies in multiple sections
- **WHEN** `audit()` is called
- **THEN** it SHALL parse dependencies from `project.dependencies`, `project.optional-dependencies`, and `dependency-groups`

#### Scenario: requirements.txt format
- **GIVEN** requirements.txt with version specifiers
- **WHEN** `audit()` is called
- **THEN** it SHALL parse package names and version constraints (e.g., `requests>=2.28.0`)

#### Scenario: package.json sections
- **GIVEN** package.json with dependencies and devDependencies
- **WHEN** `audit()` is called
- **THEN** it SHALL parse packages from both sections

