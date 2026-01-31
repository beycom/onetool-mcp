# tool-sdk Specification

> **STATUS: REMOVED**
>
> The `ot_sdk` package has been removed. Extension tools now use `ot.*` imports directly.
> Isolated tools (with PEP 723 dependencies) are fully standalone with no onetool imports.
>
> See: `tool-scaffold` spec for current template documentation.

## Purpose

This spec documented the ot_sdk package for building extension tools with isolated dependencies and JSON-RPC communication. The package was removed because isolated tools run via `uv run` and cannot reliably import `ot_sdk`.

## Requirements

### Requirement: Package Removed

The `ot_sdk` package SHALL NOT be used for new development.

#### Scenario: Extension tools use ot.* imports
- **WHEN** developing an internal extension tool
- **THEN** use `ot.*` imports directly (e.g., `from ot.config import get_secret`)

#### Scenario: Isolated tools are standalone
- **WHEN** developing an isolated tool with PEP 723 dependencies
- **THEN** the tool is fully standalone with no onetool imports
- **AND** communication happens via JSON-RPC over stdin/stdout
