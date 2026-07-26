# skill-ot-ref Specification

## Purpose

Defines the shared OneTool mechanics and central callable reference carried by `ot-ref`.

## Requirements

### Requirement: Shared reference boundary

`ot-ref` SHALL be model-invoked and SHALL own generic call syntax, discovery, aliases, recovery,
large-result handling, and live lookup fallback without replacing capability-specific judgment.

#### Scenario: Runtime state differs from the shipped reference
- **WHEN** an agent needs current pack or tool information
- **THEN** `ot-ref` SHALL direct it to the smallest relevant live discovery call

### Requirement: Complete central reference

The generated `ot-ref` pack map SHALL cover each registered pack and its aliases. Its greppable
tool index SHALL contain every canonical tool signature and one-line summary and SHALL remain
byte-identical to the documentation copy.

#### Scenario: Documentation is regenerated
- **WHEN** `just docs-sync` completes
- **THEN** the pack map and both tool-index copies SHALL reflect the runtime registry
- **AND** catalog validation SHALL fail if the index copies differ or omit an owned pack
