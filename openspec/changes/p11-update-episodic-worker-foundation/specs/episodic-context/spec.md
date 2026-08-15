## ADDED Requirements

### Requirement: Complete context is supplied at episode startup

The MCP runtime SHALL supply the complete committed episodic context to each
worker at startup. It SHALL NOT expose context search, selective-read, or
section-query operations.

#### Scenario: First episode has no stored context
- **WHEN** a worker starts for a newly created session
- **THEN** it SHALL receive an explicit empty context with revision `0`

#### Scenario: Later episode receives current context
- **GIVEN** a session has committed context
- **WHEN** its next worker starts
- **THEN** the worker SHALL receive the complete parsed context in one value
- **AND** it SHALL NOT receive prior worker messages as continuation context

### Requirement: Context uses one compact versioned schema

Committed context SHALL contain runtime-owned `schema_version` and `revision`
fields plus the required worker-maintained fields `goal`, `work`, `knowledge`,
`questions`, and `references`. Unknown fields SHALL be rejected.

`goal` SHALL contain a status of `active`, `blocked`, or `complete`, a nonblank
objective, and an ordered list of success criteria. `work` SHALL contain a
summary and ordered lists of next actions and blockers. Each `knowledge` entry
SHALL contain a kind of `fact`, `decision`, or `constraint` and nonblank text.
`questions` SHALL be an ordered list of nonblank strings. Each `references`
entry SHALL contain a project-relative file path and nonblank purpose.

#### Scenario: Valid complete context
- **WHEN** terminal output includes every required worker-maintained field with valid values
- **THEN** the MCP SHALL accept the typed object as the replacement
- **AND** the MCP SHALL add the schema version and next revision when committing it

#### Scenario: Unknown or invalid field
- **WHEN** a submitted context contains an unknown field, missing required field, invalid enum, or blank required value
- **THEN** the MCP SHALL reject it with an error identifying the affected field
- **AND** it SHALL preserve the committed context

### Requirement: Workers return at most one typed replacement

The strict worker terminal output SHALL accept one optional complete typed
`context` object. It SHALL NOT accept raw YAML, fragments, patches, item
operations, formatting choices, repair instructions, or a separate context tool.

#### Scenario: Terminal context is present
- **WHEN** valid `completed` or `needs_input` terminal output includes `context`
- **THEN** the MCP SHALL process that complete object as the next revision

#### Scenario: Terminal context is absent
- **WHEN** valid terminal output omits `context`
- **THEN** the committed context and revision SHALL remain unchanged

#### Scenario: Loaded revision changed before commit
- **WHEN** the committed revision differs from the revision loaded for the episode
- **THEN** the MCP SHALL reject the terminal context without changing committed context

### Requirement: The MCP performs deterministic context processing

The MCP SHALL own normalization, validation, canonical YAML rendering, size
measurement, revisioning, and persistence. It SHALL perform only these repairs:
normalize line endings, trailing whitespace and surrounding blank lines; remove
blank list strings and exact duplicates while retaining first-submitted order;
and normalize project-relative separators and lexical `.` path segments.

The MCP SHALL NOT infer meaning, rewrite prose, summarize, truncate, merge
similar entries, choose stale content, or ask an agent to repair formatting.

#### Scenario: Mechanically repairable submission
- **WHEN** a valid typed submission differs only in an allowed mechanical form
- **THEN** the MCP SHALL normalize it deterministically
- **AND** it SHALL render canonical UTF-8 YAML with fixed key order, LF line endings, and one final newline
- **AND** the YAML SHALL contain no comments, aliases, anchors, or custom tags

#### Scenario: Semantic repair would be required
- **WHEN** a context remains invalid or oversized after allowed normalization
- **THEN** the MCP SHALL reject it rather than modify its meaning or ask the worker to repair it

### Requirement: References remain inside the project

Every context reference SHALL resolve to an existing regular file inside the
current project root. Absolute paths, paths that escape the project, missing
files, directories, and other non-regular files SHALL be rejected.

#### Scenario: Valid project file reference
- **WHEN** a submitted relative path resolves to an existing regular project file
- **THEN** the MCP SHALL accept the reference

#### Scenario: Invalid reference
- **WHEN** a reference is absolute, escapes the project, is missing, or does not resolve to a regular file
- **THEN** the MCP SHALL reject it with an error identifying the reference path

### Requirement: Context size uses canonical encoded bytes

The MCP SHALL accept committed context only when the canonical YAML's UTF-8 byte
length is no greater than `context_max_kb * 1024`. The default
`context_max_kb` SHALL be `16`. This limit SHALL apply only to `context.yaml`,
not to total worker input, and SHALL NOT use token estimation or automatic
compaction.

#### Scenario: Context is within the configured limit
- **WHEN** canonical context size is equal to or less than the configured byte limit
- **THEN** the MCP SHALL accept the size check

#### Scenario: Context exceeds the configured limit
- **WHEN** canonical context size exceeds the configured byte limit
- **THEN** the MCP SHALL reject it with the actual byte count and configured KB limit
- **AND** it SHALL preserve the committed context

### Requirement: Startup preflight protects the last valid context

Before starting a worker, the MCP SHALL safely load the session's complete
context, apply allowed normalization, validate it strictly, validate references,
render it canonically, and measure its size. Safe noncanonical context SHALL be
rewritten atomically in canonical form.

#### Scenario: Stored context is safe but noncanonical
- **WHEN** preflight loads structurally valid context in a noncanonical form
- **THEN** the MCP SHALL rewrite it atomically in canonical form
- **AND** worker startup SHALL continue with the validated parsed context

#### Scenario: Stored context cannot pass preflight
- **WHEN** stored context is unsafe or unreadable YAML, schema-invalid, oversized, or contains an invalid reference
- **THEN** `worker.run` SHALL return `failed` with the affected field or path
- **AND** no worker thread SHALL start
- **AND** the existing context file SHALL otherwise remain unchanged

### Requirement: Context commits are atomic and outcome-dependent

Committed context SHALL live at
`episodic-context/<session-id>/context.yaml` under the current OneTool
project-state directory. A successful episode SHALL atomically commit its valid
terminal context with an incremented revision. Failed or interrupted episodes
SHALL preserve the committed file.

#### Scenario: Successful episode with terminal context
- **WHEN** an episode finishes as `completed` or `needs_input` with valid terminal context
- **THEN** the MCP SHALL recheck its expected revision
- **AND** it SHALL atomically replace `context.yaml` with the canonical next revision

#### Scenario: Successful episode without terminal context
- **WHEN** an episode finishes as `completed` or `needs_input` without terminal context
- **THEN** the committed context and revision SHALL remain unchanged

#### Scenario: Episode does not complete successfully
- **WHEN** an episode fails or is interrupted
- **THEN** the committed context and revision SHALL remain unchanged

### Requirement: Context remains private to workers in its session

Committed Context SHALL be supplied automatically only to fresh workers in the
same session. The MCP SHALL NOT return the Context body through `worker.run`,
Status, Console, History, or the main conversation.

#### Scenario: Episode returns to the main agent
- **WHEN** an episode reaches any terminal status
- **THEN** the public result SHALL NOT contain Context or a Context summary
- **AND** a later fresh worker in the same session SHALL still receive the complete committed Context

### Requirement: Each episode appends mechanical History

After terminal handling and Local Changes observation, the MCP SHALL append one
canonical versioned JSON record to
`episodic-context/<session-id>/history.jsonl`. The MCP SHALL be the sole History
writer. Each record SHALL contain only the episode ID, UTC timestamps, terminal
status, turn count, Context revisions before and after, Console message IDs and
kinds, Local Changes observation state and changed path classifications, optional
bounded failure classification, and bounded warning codes.

History SHALL NOT contain Chat text, agent-authored narrative, Context bodies,
Console bodies, file contents, diffs, tool results, or intermediate reasoning.

#### Scenario: Terminal episode is recorded
- **WHEN** terminal processing and the final project scan complete
- **THEN** the MCP SHALL append exactly one History record for that episode
- **AND** it SHALL flush and `fsync` the journal before returning Status

#### Scenario: Episode has Console output and Local Changes
- **WHEN** the worker publishes Console messages and changes project files
- **THEN** History SHALL contain only the Console message IDs and kinds plus sorted project-relative path classifications
- **AND** History SHALL contain none of the corresponding bodies, contents, or diffs

#### Scenario: History append fails
- **WHEN** the MCP cannot append or durably flush the History record
- **THEN** the known worker, Console, Context, and Local Changes outcomes SHALL remain unchanged
- **AND** Status SHALL include a bounded History warning

### Requirement: History readers preserve a valid journal prefix

History records SHALL use a strict schema version and reject unknown fields.
A reader SHALL preserve every complete valid earlier record when an interrupted
append leaves one malformed final line, but SHALL reject malformed non-final
records.

#### Scenario: Final append is interrupted
- **WHEN** `history.jsonl` ends with one malformed partial line after valid records
- **THEN** an explicit History read SHALL return the valid prefix
- **AND** it SHALL identify the ignored final line as incomplete

#### Scenario: Interior record is malformed
- **WHEN** a malformed History record is followed by another line
- **THEN** the explicit History read SHALL fail rather than silently skip the record
