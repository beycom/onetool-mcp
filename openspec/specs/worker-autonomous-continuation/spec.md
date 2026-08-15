# Worker Autonomous Continuation Specification

## Purpose

Defines bounded internal same-thread continuation within one synchronous worker
episode, including later-turn input, total limits, terminal Context handling,
fresh episodes after user input, and mechanical turn-count recording.

## Requirements

### Requirement: Continuation is internal to one worker episode

An internal `continue` outcome SHALL be valid only when the worker needs no user
input and has concrete remaining work. The outcome SHALL contain one bounded
`next_action` and SHALL NOT contain Context, a Console body, a public Status
message, or an authority change. `worker.run` SHALL NOT expose `continue`
as a public status.

#### Scenario: Worker can continue autonomously
- **WHEN** a turn returns valid internal `continue` before any episode limit
- **THEN** the runtime SHALL start another turn on the same worker thread
- **AND** the public caller SHALL receive no intermediate result

#### Scenario: Continuation output is invalid
- **WHEN** `continue` includes terminal Context, a user question, or an unknown field
- **THEN** the episode SHALL fail through terminal validation

### Requirement: Later turns receive only fixed ephemeral continuation input

The first turn SHALL receive the current Chat request and complete selected
Context. A later turn SHALL receive only the fixed continuation instruction and
the preceding `next_action` through the same thread. The runtime SHALL preserve
the original effective authority and SHALL NOT reinject Chat, Context, History,
Console, Local Changes observations, or Status.

#### Scenario: Second turn begins
- **WHEN** the first turn returns valid `continue`
- **THEN** the second turn SHALL use the same thread and effective authority
- **AND** Chat and committed Context SHALL NOT be supplied again

### Requirement: Continuation obeys a turn limit and total deadline

One episode SHALL have a strict configured maximum turn count and one monotonic
deadline covering all turns and lifecycle work. The deadline SHALL NOT reset
between turns.

#### Scenario: Turn limit is reached
- **WHEN** the final permitted turn returns `continue`
- **THEN** `worker.run` SHALL return `failed` with bounded `turn_limit` classification
- **AND** it SHALL NOT commit Context or start another turn

#### Scenario: Total deadline expires
- **WHEN** no terminal outcome is accepted before the episode deadline
- **THEN** `worker.run` SHALL return `failed` with bounded `episode_timeout` classification
- **AND** it SHALL not replay any earlier turn

### Requirement: Context commits only at terminal outcomes

The runtime SHALL commit an optional complete replacement for the selected
Context only from final `completed` or `needs_input`. It SHALL NOT checkpoint
Context from `continue` or preserve a partial later-turn submission.

#### Scenario: Multiple turns complete
- **WHEN** one or more `continue` turns are followed by valid `completed` with Context
- **THEN** the runtime SHALL validate and commit that final complete Context once

#### Scenario: Later turn fails
- **WHEN** a later turn fails or is interrupted
- **THEN** committed Context SHALL remain at the pre-episode revision
- **AND** prior project, Console, or external effects SHALL not be replayed or claimed as rolled back

### Requirement: User input always starts a fresh episode

`needs_input` SHALL terminate continuation, delete the current thread, and finish
the episode. The user's answer SHALL start a distinct episode and thread with the
same named committed Context.

#### Scenario: Continued worker requests input
- **WHEN** any turn returns valid `needs_input`
- **THEN** no further turn SHALL start on that thread
- **AND** the answer SHALL be processed by a fresh worker thread

### Requirement: History records the actual turn count

The mechanical episode History record SHALL contain the number of model turns
started in that episode and SHALL not contain continuation instructions or
same-thread messages.

#### Scenario: Episode uses three turns
- **WHEN** two internal continuations precede a terminal third turn
- **THEN** History SHALL record `turn_count` as `3`
- **AND** it SHALL contain no `next_action` or thread transcript
