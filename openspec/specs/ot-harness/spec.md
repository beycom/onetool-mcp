# ot-harness Specification

## Purpose

Define the Harbor-backed Codex benchmark harness package, configuration model, runtime boundary, result normalization, reporting, and documentation requirements.

## Requirements

### Requirement: Harness package

The system SHALL provide a standalone `ot-harness` package under `packages/ot-harness/` for Harbor-backed Codex benchmark experiments.

#### Scenario: Package exists separately from legacy benchmark harness

- **WHEN** a developer inspects the repository packages
- **THEN** `packages/ot-harness/` exists as the permanent source, config, test, and documentation location for the Harbor-backed harness
- **AND** `packages/onetool-bench/` remains present and unchanged by the initial `ot-harness` implementation

### Requirement: Command-line interface

The system SHALL provide an `ot-harness` command-line interface with `validate`, `run`, and `report` commands.

#### Scenario: Validate experiment config

- **WHEN** a user runs `ot-harness validate <experiment.yaml>` with a valid experiment config
- **THEN** the command validates the experiment file, referenced task file, referenced variant files, local paths, and required config fields
- **AND** the command exits successfully without starting a benchmark run

#### Scenario: Reject invalid config

- **WHEN** a user runs `ot-harness validate <experiment.yaml>` with unknown fields, invalid values, missing task files, or missing variant files
- **THEN** the command exits unsuccessfully with a clear validation error

#### Scenario: Run experiment matrix

- **WHEN** a user runs `ot-harness run <experiment.yaml>` with a valid experiment config
- **THEN** the command orchestrates Harbor runs for each configured task, variant, and repetition
- **AND** it writes generated runtime output under the configured output root

#### Scenario: Report run output

- **WHEN** a user runs `ot-harness report <run-output-dir>` for a completed or partially completed run
- **THEN** the command parses available Harbor outputs and emits concise per-variant summary data

### Requirement: Experiment config

The system SHALL define a strict experiment config that describes the benchmark matrix, Harbor execution settings, fixed task list, variants, repetitions, timeouts, output root, and required metric expectations.

#### Scenario: Resolve experiment-relative paths

- **WHEN** an experiment config references task or variant paths
- **THEN** the system resolves those paths relative to the experiment config file

#### Scenario: Use fixed task slice across variants

- **WHEN** an experiment runs multiple variants
- **THEN** every variant uses the same fixed task list for the experiment

#### Scenario: Reject legacy bench config fields

- **WHEN** an experiment or variant config contains fields from the legacy `packages/onetool-bench/` config model that are not part of the `ot-harness` schema
- **THEN** the system rejects the config instead of treating those fields as aliases

### Requirement: Codex variants

The system SHALL support initial Codex benchmark variants for base Codex, Codex with OneTool MCP, and Codex with skill directories.

#### Scenario: Base Codex variant

- **WHEN** an experiment includes the `codex-base` variant
- **THEN** the generated Harbor configuration uses the same Codex agent and model as the experiment matrix
- **AND** it does not configure OneTool MCP
- **AND** it does not configure skills except for a neutral empty skill directory if Harbor or Codex requires one

#### Scenario: OneTool MCP variant

- **WHEN** an experiment includes the `codex-onetool-mcp` variant
- **THEN** the generated Harbor configuration uses the same Codex agent and model as the base variant
- **AND** it configures a OneTool MCP server for the Codex run
- **AND** it does not require handoff tools

#### Scenario: Skills variant

- **WHEN** an experiment includes a `codex-skills-*` variant
- **THEN** the generated Harbor configuration uses the same Codex agent and model as the other variants
- **AND** it points Harbor skill injection at the configured skill directory
- **AND** the result metadata records the skill variant id, skill path, deterministic skill text hash, and available skill metadata

### Requirement: Runtime artifact locations

The system SHALL default generated Harbor jobs, raw results, scratch files, and logs to `tmp/harness/harbor/`, while allowing the experiment config to override the output root to a location outside `packages/ot-harness/`.

#### Scenario: Default output root

- **WHEN** an experiment config does not specify an output root
- **THEN** generated runtime artifacts are written under `tmp/harness/harbor/`

#### Scenario: Package excludes raw runtime output

- **WHEN** a benchmark run produces Harbor jobs, copied task environments, raw logs, trajectories, or scratch outputs
- **THEN** those raw runtime artifacts are not written under `packages/ot-harness/`

#### Scenario: Reject package-internal output root

- **WHEN** an experiment config sets the output root to a path that resolves inside `packages/ot-harness/`
- **THEN** validation rejects the config with a clear error

### Requirement: Harbor execution boundary

The system SHALL use Harbor as the benchmark execution engine for benchmark runs.

#### Scenario: Generate Harbor execution command

- **WHEN** a valid experiment matrix is prepared for a variant
- **THEN** the system creates the Harbor command or Harbor-compatible run configuration needed to execute that matrix

#### Scenario: Verify local execution dependencies

- **WHEN** a user prepares to run benchmarks locally
- **THEN** the documentation or diagnostics identify commands for checking Harbor, Harbor run support, available datasets, Codex, Docker, OneTool MCP, and skill injection readiness

### Requirement: Trial result normalization

The system SHALL normalize Harbor job or trial outputs into per-trial result records with task, variant, repetition, accuracy, timing, token, cost, tool-call, artifact, and source-path fields when available.

#### Scenario: Normalize successful trial

- **WHEN** Harbor output contains verifier output, timing fields, token fields, cost fields, final output, logs path, and result JSON path
- **THEN** the normalized trial result includes those fields for the task, variant, and repetition

#### Scenario: Missing verifier output

- **WHEN** Harbor output for a trial lacks verifier output needed for accuracy comparison
- **THEN** the normalized trial result marks accuracy as invalid
- **AND** the report does not count that trial as a model accuracy failure

#### Scenario: Missing token or cost telemetry

- **WHEN** Harbor output for a trial lacks token or cost fields
- **THEN** the normalized trial result marks token or cost telemetry as partial or unavailable
- **AND** it does not silently replace missing values with zero

### Requirement: Aggregated reports

The system SHALL aggregate normalized trial results by variant and produce comparison reports with accuracy, invalid/tooling failure, timing, token, cost, tool-call, and OneTool-call metrics when available.

#### Scenario: Compare configured variants

- **WHEN** a report is generated for a run containing `codex-base`, `codex-onetool-mcp`, and `codex-skills-*` variants
- **THEN** the report includes a comparison table with one column per variant

#### Scenario: Include core aggregate metrics

- **WHEN** normalized trial data is available
- **THEN** the report includes task count, repetition count, trial count, pass rate, partial rate, invalid rate, mean score or reward, mean wall time, median wall time, mean token counts, mean cost, total cost, and tooling failure rate where those fields are available

### Requirement: Documentation

The system SHALL document the purpose, setup, Harbor dependency, relationship to `packages/onetool-bench/`, smoke run workflow, artifact locations, report interpretation, and known limitations of `ot-harness`.

#### Scenario: Read package README

- **WHEN** a developer reads `packages/ot-harness/README.md`
- **THEN** it explains what `ot-harness` is, why Harbor is the execution engine, how to validate local dependencies, how to run the smoke experiment, where generated artifacts go, how to read reports, and which scope is deferred
