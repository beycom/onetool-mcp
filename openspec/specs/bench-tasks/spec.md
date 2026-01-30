# bench-tasks Specification

## Purpose

Defines the scenario and task structure for bench, including task types, multi-prompt tasks, and type-specific defaults.

---

## Requirements

### Requirement: Scenario and Task Structure

The harness SHALL organize tasks into scenarios.

#### Scenario: Scenario definition
- **GIVEN** a scenario with name, description, and tasks
- **WHEN** the harness runs
- **THEN** it SHALL execute all tasks in the scenario

#### Scenario: Task definition
- **GIVEN** a task with name, prompt, and optional server
- **WHEN** the harness runs the task
- **THEN** it SHALL send the prompt to the LLM with access to the specified server

#### Scenario: Task without server (baseline)
- **GIVEN** a task with `server: null` or no server
- **WHEN** the task runs
- **THEN** it SHALL run without MCP server access (baseline test)

#### Scenario: Task with multiple servers
- **GIVEN** a task with `server: [server1, server2]`
- **WHEN** the task runs
- **THEN** it SHALL provide access to all specified servers

#### Scenario: Task tags
- **GIVEN** a task with `tags: [focus, important]`
- **WHEN** the harness runs with `--tags focus`
- **THEN** it SHALL only run tasks matching the tag filter

### Requirement: Task Types

The harness SHALL support two task types within a single `run` command.

#### Scenario: Task type determines execution

- **WHEN** a task has `type: direct`
- **THEN** the system invokes the MCP tool directly without LLM

- **WHEN** a task has `type: harness`
- **THEN** the system runs an LLM benchmark with optional MCP server

#### Scenario: Default task type

- **WHEN** a task does not specify `type`
- **THEN** the system defaults to `type: harness`

#### Scenario: Mix task types in scenario

- **WHEN** a scenario contains tasks with different types
- **THEN** the system executes each task according to its type
- **AND** reports results for all tasks

### Requirement: Direct Task Type

The system SHALL support `type: direct` for direct MCP tool invocation.

#### Scenario: Execute direct task

- **WHEN** a task has `type: direct` with `server`, `tool`, and `arguments`
- **THEN** the system connects to the specified MCP server
- **AND** invokes the tool with the given arguments
- **AND** returns the tool result

### Requirement: Type-Specific Defaults

The system SHALL support nested defaults for each task type.

#### Scenario: Type defaults

- **WHEN** defaults specify `direct` or `harness` configuration
- **THEN** tasks of that type inherit the defaults
- **AND** tasks can override individual settings

### Requirement: Multi-Prompt Tasks

The harness SHALL support tasks with one or more sequential prompts to enable controlled multi-turn benchmarking.

#### Scenario: Split prompt on delimiter
- **GIVEN** a task YAML with `prompt` field containing `---PROMPT---` delimiter(s)
- **WHEN** the runner processes the task
- **THEN** it SHALL split the prompt into multiple prompts on `---PROMPT---`
- **AND** strip whitespace from each resulting prompt

#### Scenario: Single prompt without delimiter
- **GIVEN** a task YAML with `prompt` field containing no `---PROMPT---` delimiter
- **WHEN** the runner processes the task
- **THEN** it SHALL treat the entire prompt as a single prompt (existing behaviour)

#### Scenario: Execute prompts sequentially
- **GIVEN** a task with N prompts (split from `prompt` field)
- **WHEN** the task executes
- **THEN** the runner SHALL send prompt 1 and wait for its agentic loop to complete
- **AND** then send prompt 2 with accumulated conversation history
- **AND** continue until all N prompts are processed

#### Scenario: Accumulate conversation history across prompts
- **GIVEN** a multi-prompt task where prompt 1 triggers tool calls
- **WHEN** prompt 2 is sent
- **THEN** the message history SHALL include prompt 1, its tool calls, tool results, and LLM response
- **AND** prompt 2 is appended to this history

#### Scenario: Track metrics across all prompts
- **GIVEN** a multi-prompt task
- **WHEN** the task completes
- **THEN** `TaskResult.llm_call_metrics` SHALL include entries for all LLM calls across all prompts
- **AND** total token counts SHALL reflect the full task execution
