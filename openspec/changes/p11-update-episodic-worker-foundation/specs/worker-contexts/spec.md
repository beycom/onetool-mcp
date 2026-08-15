## ADDED Requirements

### Requirement: Contexts are named project-local files

Worker Contexts SHALL be scoped to the effective project CWD and stored as
individual UTF-8 Markdown files at
`.onetool/state/worker/contexts/<context>.md`. Context names SHALL be lowercase
filesystem-safe slugs and SHALL NOT contain separators, traversal, control
characters, or ambiguous normalized forms.

The name `default` SHALL identify the initial Context for every newly invoked
orchestrator. The runtime SHALL create a missing active Context atomically when
`worker.run`, `worker.select`, or `worker.update_context` first names it. It SHALL
NOT expose a contextless worker mode or create a project registry.

#### Scenario: First worker call uses the default Context
- **WHEN** an orchestrated Chat starts without an earlier selection
- **THEN** its effective Context SHALL be `default`
- **AND** the runtime SHALL create `default.md` if it does not exist

#### Scenario: A new review Context is named
- **WHEN** `worker.run` names valid missing Context `review-feature-x`
- **THEN** the runtime SHALL atomically create that Context before worker startup
- **AND** the worker SHALL receive an empty semantic body rather than another Context's state

#### Scenario: Context name is invalid
- **WHEN** an operation supplies an invalid Context name
- **THEN** it SHALL fail without creating, finding, or modifying a file

### Requirement: Context frontmatter is strict discoverable metadata

Every Context file SHALL contain YAML frontmatter with exactly runtime-owned
`schema_version`, `revision`, and `status` plus user-visible `description` and
`tags`. Schema version SHALL be `1`, revision SHALL be a positive integer, status
SHALL be `active` or `archived`, description SHALL be a bounded string, and tags
SHALL be a bounded ordered list of unique nonblank strings.

The filename SHALL be the Context identity; the body SHALL NOT duplicate or
override the name. Malformed YAML, aliases, unknown fields, invalid encoding,
invalid values, and oversized files SHALL fail preflight without repair by an
agent.

#### Scenario: Context metadata is listed
- **WHEN** `worker.list_contexts` is called
- **THEN** it SHALL return validated Context name, description, tags, status, and revision in stable name order
- **AND** it SHALL NOT return the Markdown body

#### Scenario: Stored frontmatter is invalid
- **WHEN** a Context file cannot pass strict frontmatter validation
- **THEN** an operation targeting it SHALL fail without rewriting the file

### Requirement: Context bodies contain complete current state

The Markdown body SHALL represent complete current semantic state for later
workers using that name. It SHALL be current state rather than a transcript,
prompt log, tool-result log, Console copy, History copy, or source-file copy.

At episode startup, the runtime SHALL supply the complete validated body for only
the selected Context, explicitly delimited as untrusted state data. The body
SHALL NOT override the current request, project instructions, worker instructions,
authority, or approval policy.

#### Scenario: Later worker uses the same Context
- **GIVEN** Context `feature-x` has a committed body
- **WHEN** a later episode selects `feature-x`
- **THEN** it SHALL receive the complete current `feature-x` body
- **AND** it SHALL NOT receive prior worker messages or another Context body

#### Scenario: Fresh review Context starts
- **GIVEN** `feature-x` contains implementation state
- **WHEN** a worker starts with newly created Context `review-feature-x`
- **THEN** it SHALL receive the shared project files and instructions
- **AND** it SHALL receive none of the `feature-x` semantic body

### Requirement: Context replacement is bounded and atomic

A successful worker terminal output MAY propose one complete replacement body.
The runtime SHALL normalize permitted line endings and trailing whitespace,
validate UTF-8, validate project-contained file references, render canonical
frontmatter, and enforce `context_max_kb` against the complete encoded file.

The runtime SHALL bind replacement to both the loaded revision and loaded file
digest, increment revision exactly once, and atomically replace the file beside
its prior version. Omitted replacement SHALL preserve body and revision. Failed
or interrupted episodes and invalid replacements SHALL preserve the last valid
file.

#### Scenario: Valid replacement is committed
- **WHEN** an active Context episode completes with a valid bounded replacement
- **THEN** the runtime SHALL atomically commit it as the next revision

#### Scenario: User edits the Context during an episode
- **WHEN** the stored revision or digest differs from the episode's loaded value
- **THEN** terminal Context commit SHALL fail without overwriting the manual edit

#### Scenario: Replacement is oversized
- **WHEN** the canonical complete Context exceeds `context_max_kb * 1024` UTF-8 bytes
- **THEN** the episode SHALL fail and preserve the prior revision

### Requirement: Context metadata updates use explicit upsert semantics

`worker.update_context` SHALL require a Context name and at least one of
`description` or `tags`. It SHALL create a missing active Context and update only
the supplied metadata. Omitted fields SHALL preserve current values; an explicit
empty description or empty tag list SHALL clear that field; supplied tags SHALL
replace the complete list rather than merge implicitly.

Metadata update SHALL preserve the semantic body, increment revision exactly
once, and use the same digest check and atomic replacement as a worker commit.

#### Scenario: Metadata creates a Context
- **WHEN** update names a missing valid Context with description or tags
- **THEN** it SHALL create an active Context with an empty semantic body
- **AND** it SHALL report that creation occurred

#### Scenario: Tags are replaced
- **GIVEN** an active Context has existing tags
- **WHEN** update supplies a different complete tag list
- **THEN** the stored tags SHALL exactly equal the supplied normalized list
- **AND** description and semantic body SHALL remain unchanged

### Requirement: Archival preserves Context identity and content

`worker.archive_context` SHALL require an existing active non-default Context. It
SHALL atomically set status to `archived`, increment revision, and preserve the
description, tags, and semantic body. It SHALL NOT delete or move the file.

Archived Contexts SHALL remain visible through listing but SHALL fail `run` and
`select`. Their names SHALL remain reserved, so automatic creation SHALL NOT
replace or reactivate them. Archiving `default`, an unknown name, or an already
archived Context SHALL fail without changing files.

#### Scenario: Active Context is archived
- **WHEN** archive targets an existing active Context other than `default`
- **THEN** listing SHALL report it as archived with its metadata intact
- **AND** later run or select operations SHALL reject it

#### Scenario: Archived name is used again
- **WHEN** run, select, or update names an archived Context
- **THEN** the operation SHALL fail rather than create or reactivate that name

### Requirement: Context bodies remain private across channels

The runtime SHALL NOT return or copy a Context body through `worker.run`,
`worker.select`, `worker.list_contexts`, `worker.update_context`,
`worker.archive_context`, Status, Console, History, telemetry, or the main
conversation. Description, tags, status, revision, and name are metadata and MAY
be returned only by the specified Context operations.

#### Scenario: Main agent lists Contexts
- **WHEN** the main agent calls `worker.list_contexts`
- **THEN** it SHALL receive bounded frontmatter metadata
- **AND** it SHALL receive no semantic body or body summary

### Requirement: Every episode appends project-scoped mechanical History

After terminal handling, cleanup, and Local Changes observation, the runtime
SHALL append one canonical History record to
`.onetool/state/worker/history.jsonl`. Each strict record SHALL contain only
runtime-observed episode ID, selected Context name, timestamps, terminal status,
turn count, Context revisions before and after, Console message identifiers and
kinds, Local Changes path classifications, optional bounded failure
classification, and bounded warning codes.

History SHALL NOT contain prompts, descriptions, tags, Context bodies, Console
bodies, file contents, diffs, tool results, or agent-authored narrative.

#### Scenario: Episode reaches terminal handling
- **WHEN** terminal processing and final Local Changes observation finish
- **THEN** the runtime SHALL append exactly one History record for that episode
- **AND** the record SHALL identify the effective Context name without copying its metadata or body

#### Scenario: Final History line is interrupted
- **WHEN** an explicit History reader encounters one malformed final line after a valid prefix
- **THEN** it SHALL return the valid prefix and ignore only that final line

#### Scenario: History append fails
- **WHEN** the runtime cannot append or durably flush History
- **THEN** known worker, Console, Context, and Local Changes outcomes SHALL remain unchanged
- **AND** Status SHALL include a bounded History warning
