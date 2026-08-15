# skill-use-worker Specification

## Purpose

Defines explicit main-agent coordination through fresh worker episodes, one
Chat-selected named Context, and strict Status and Console channel isolation.

## Requirements

### Requirement: The use-worker skill is an explicit coordinator

The `use-worker` skill SHALL activate only when explicitly invoked. While active,
the main agent SHALL coordinate the user conversation and delegate
substantive inspection, planning, editing, execution, and verification through
`worker.run` rather than performing that work itself.

#### Scenario: Skill is invoked
- **WHEN** the user explicitly invokes `use-worker`
- **THEN** the main agent SHALL delegate substantive project work through fresh worker episodes

### Requirement: Every Chat starts with selected Context default

For each invocation, `use-worker` SHALL retain exactly one selected Context
name as coordinator state and SHALL initialize it to `default`. It SHALL supply
that selected name explicitly to every run that lacks a one-episode override.

The selected name SHALL remain Chat-local coordinator state. It SHALL NOT be
stored as a project-global or process-global default and SHALL NOT expose the
Context body to the main agent.

#### Scenario: First delegated episode
- **WHEN** an invoked orchestrator delegates before any selection change
- **THEN** it SHALL run with Context `default`

#### Scenario: Another Chat starts
- **GIVEN** an earlier Chat selected `feature-x`
- **WHEN** a new `use-worker` invocation starts
- **THEN** the new Chat SHALL select `default` rather than inherit `feature-x`

### Requirement: worker.select changes only the current Chat selection

When the user or coordinator invokes `worker.select`, `use-worker` SHALL
retain the returned active Context name for later runs in that Chat. Selecting a
missing name MAY create its Context. Selecting an archived or invalid name SHALL
fail without changing the retained selection.

#### Scenario: User changes topics
- **GIVEN** the selected Context is `feature-x`
- **WHEN** select succeeds for `feature-y`
- **THEN** later runs without overrides SHALL use `feature-y`

#### Scenario: Selection fails
- **WHEN** select rejects an invalid or archived Context
- **THEN** the previously selected Context SHALL remain active for the Chat

### Requirement: Explicit run Context is a one-episode override

When a run explicitly names a Context, `use-worker` SHALL use that Context
only for the current episode and SHALL preserve the Chat selection.

#### Scenario: Fresh review uses another Context
- **GIVEN** the Chat selection is `feature-x`
- **WHEN** run explicitly names newly created `review-feature-x`
- **THEN** the review SHALL receive no `feature-x` semantic body
- **AND** the next run without an override SHALL use `feature-x`

### Requirement: The use-worker skill relays only bounded Status

The main agent SHALL relay only the bounded worker Status receipt, diagnostic, or
question. It SHALL NOT request, read, reproduce, or summarize Context or Console
bodies. Substantial completed output SHALL reach the user through Console.

For `needs_input`, the main agent SHALL ask the returned question and send the
answer to a fresh episode with the same effective Context name.

#### Scenario: Worker reaches a terminal outcome
- **WHEN** run returns completed, failed, or interrupted
- **THEN** the main agent SHALL report only its bounded Status

#### Scenario: Worker needs input
- **WHEN** run returns `needs_input`
- **THEN** the main agent SHALL present its single question
- **AND** the answer SHALL use the same Context in a fresh worker thread
