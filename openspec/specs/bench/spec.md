# bench Specification

## Purpose

Defines the core structure and conventions for the OneTool benchmark harness. The harness runs LLM benchmarks against MCP servers and evaluates responses using deterministic matching or LLM-as-judge evaluation.

For detailed requirements, see the feature-specific specs:

| Spec | Purpose |
|------|---------|
| [bench-config](../bench-config/spec.md) | YAML configuration, server connections, secrets |
| [bench-evaluators](../bench-evaluators/spec.md) | Named evaluators, deterministic and LLM-as-judge |
| [bench-tasks](../bench-tasks/spec.md) | Scenarios, task types, multi-prompt tasks |
| [bench-metrics](../bench-metrics/spec.md) | Per-call metrics, context growth analysis |
| [bench-csv](../bench-csv/spec.md) | CSV results export |
| [bench-tui](../bench-tui/spec.md) | TUI favorites mode, harness config file |
| [bench-logging](../bench-logging/spec.md) | CLI output, verbose/trace modes, console reporter |

---

## Requirements

### Requirement: Comparison Benchmark Structure

The harness SHALL support a main comparison benchmark (`compare.yaml`) that demonstrates OneTool's value proposition by testing the same task across multiple configurations.

#### Scenario: Compare base vs MCP vs OneTool
- **GIVEN** a benchmark file with tasks targeting different server configurations
- **WHEN** the benchmark runs
- **THEN** it SHALL execute tasks for:
  - Base (no server) - LLM knowledge only
  - Single MCP (one server)
  - All MCPs (multiple servers) - demonstrates context rot
  - OneTool (optimised single tool)
- **AND** results SHALL be comparable across configurations

### Requirement: Per-Tool Benchmark Organisation

The harness SHALL support tool-specific benchmarks using the `tool_<name>.yaml` naming convention.

#### Scenario: Tool benchmark file location
- **GIVEN** a benchmark file at `bench/tool_<tool-name>.yaml`
- **WHEN** `bench run bench/tool_<tool-name>.yaml` is executed
- **THEN** it SHALL load and run the benchmark
- **AND** the benchmark SHALL focus on demonstrating OneTool capabilities

#### Scenario: Tool benchmark structure
- **GIVEN** a per-tool benchmark file
- **WHEN** it defines tasks
- **THEN** it SHALL demonstrate OneTool tool capabilities
- **AND** use simple regex evaluators where possible
- **AND** NOT include base (no server) comparison tasks
- **AND** NOT include MCP comparison tasks unless comparing efficiency

#### Scenario: Regex evaluators preferred
- **GIVEN** a tool benchmark task
- **WHEN** evaluation can be deterministic
- **THEN** it SHALL use regex evaluators (fast, deterministic)
- **AND** avoid LLM-as-judge evaluation

---

### Requirement: All MCPs Context Demonstration

The harness SHALL support registering multiple MCP servers to demonstrate context rot and token bloat.

#### Scenario: Register all available MCPs
- **GIVEN** a benchmark file with `server: [server1, server2, ..., serverN]`
- **WHEN** the harness initialises servers
- **THEN** it SHALL connect to all specified servers
- **AND** the LLM SHALL have access to all tools from all servers
- **AND** this demonstrates the token cost of loading multiple MCP tool definitions

### Requirement: Benchmark Conventions

Benchmark files SHALL follow consistent conventions for maintainability and clarity.

#### Scenario: Comparison benchmark system prompt
- **GIVEN** a comparison benchmark (`compare.yaml`, `tool_*.yaml`)
- **WHEN** it defines defaults
- **THEN** it SHALL use NO system prompt
- **REASON** Simulates realistic real-world MCP vs OneTool comparison

#### Scenario: Standard invocation format
- **GIVEN** a benchmark task (except invocation method tests)
- **WHEN** invoking OneTool
- **THEN** it SHALL use `__run` + code fence format
- **AND** code SHALL use explicit return as the final expression

#### Scenario: Task naming convention
- **GIVEN** a benchmark task
- **WHEN** defining the task name
- **THEN** it SHALL follow `category:subcategory:detail` pattern
- **EXAMPLE** `compare:base`, `tool:brave:search`, `exec:loop:range`

#### Scenario: Consistent tag taxonomy
- **GIVEN** a benchmark task
- **WHEN** defining tags
- **THEN** tags SHALL use the standard taxonomy:
  - Purpose: `compare`, `tool`, `feature`, `exec`, `error`
  - Server: `base`, `mcp`, `onetool`, `all-mcps`
  - Tool: `brave`, `context7`, `web-fetch`, `package`, `code-search`, `transform`
  - Feature: `invoke`, `proxy`, `snippet`, `direct`, `harness`
  - Execution: `parse`, `var`, `loop`, `if`, `comp`, `import`, `return`

### Requirement: Enhanced Reporter Output

The harness reporter SHALL display context growth information when relevant.

#### Scenario: Show context columns in verbose mode
- **GIVEN** user runs with `--verbose` flag
- **WHEN** results table is displayed
- **THEN** additional columns SHALL show per-call input tokens
- **AND** context growth average

#### Scenario: Display context efficiency summary
- **GIVEN** a scenario with multiple server configurations (e.g., multiple-mcp vs onetool)
- **WHEN** results are displayed
- **THEN** the reporter MAY show a summary comparing context efficiency
- **EXAMPLE** "onetool uses 4% of multiple-mcp context"

## Schema Reference

### HarnessConfig (Root)

```yaml
defaults:
  timeout: 120           # Default timeout in seconds
  model: "openai/gpt-5-mini"  # Default LLM model
  system_prompt: null    # Optional system prompt for all tasks

servers:
  <name>:
    type: stdio | http
    # For stdio:
    command: "uv"
    args: ["run", "ot"]
    env: {"KEY": "value"}
    # For http:
    url: "http://localhost:8080"
    headers: {"Authorization": "Bearer ${TOKEN}"}
    # Common:
    timeout: 30          # Connection timeout override

evaluators:
  <name>:
    expected: "value"    # Deterministic match
    prompt: "..."        # LLM evaluation prompt
    model: "..."         # LLM model for evaluation

scenarios:
  - name: "Scenario Name"
    description: "Optional description"
    tasks:
      - name: "Task Name"
        type: harness | direct  # Task type (default: harness)
        prompt: "Prompt to send to LLM"  # For harness tasks
        tool: "tool_name"                # For direct tasks
        arguments: {...}                 # For direct tasks
        server: <server-name> | [<server1>, <server2>] | null
        timeout: 60        # Task-specific timeout
        model: "..."       # Model override
        tags: [tag1, tag2]
        evaluate:
          expected: "value"
          # OR
          prompt: "..."
          model: "..."
          # OR reference named evaluator:
        evaluate: <evaluator-name>
```
