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

