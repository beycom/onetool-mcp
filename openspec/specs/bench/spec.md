# ot-bench Specification

## Purpose

Defines the YAML configuration schema for the OneTool benchmark harness. The harness runs LLM benchmarks against MCP servers and evaluates responses using deterministic matching or LLM-as-judge evaluation.
## Requirements
### Requirement: YAML Configuration File

The harness SHALL load benchmark configuration from a YAML file.

#### Scenario: Load harness configuration
- **GIVEN** a YAML file with harness configuration
- **WHEN** `ot-bench run <file>` is executed
- **THEN** it SHALL parse and validate the configuration

#### Scenario: Multiple files via glob pattern
- **GIVEN** a glob pattern like `demo/bench/*.yaml`
- **WHEN** `ot-bench run demo/bench/*.yaml` is executed
- **THEN** it SHALL expand the pattern to matching files
- **AND** run benchmarks for each file sequentially
- **AND** aggregate results across all files

#### Scenario: Multiple explicit files
- **GIVEN** multiple file paths
- **WHEN** `ot-bench run file1.yaml file2.yaml` is executed
- **THEN** it SHALL run benchmarks for each file in order

#### Scenario: Missing configuration file
- **GIVEN** a non-existent file path
- **WHEN** the harness attempts to load it
- **THEN** it SHALL fail with FileNotFoundError

#### Scenario: Variable expansion from secrets
- **GIVEN** a configuration containing `${VAR_NAME}` patterns
- **WHEN** the configuration is loaded
- **THEN** it SHALL expand variables using bench-secrets.yaml only
- **AND** support `${VAR_NAME:-default}` syntax for defaults
- **AND** error if variable not found without default

### Requirement: Defaults Configuration

The harness SHALL support default values for tasks.

#### Scenario: Default timeout
- **GIVEN** no timeout specified on a task
- **WHEN** the task runs
- **THEN** it SHALL use the defaults.timeout value
- **DEFAULT** 120 seconds

#### Scenario: Default model
- **GIVEN** no model specified on a task
- **WHEN** the task runs with an LLM
- **THEN** it SHALL use the defaults.model value
- **DEFAULT** openai/gpt-5-mini

#### Scenario: System prompt
- **GIVEN** defaults.system_prompt configured
- **WHEN** tasks run
- **THEN** the system prompt SHALL be prepended to all task prompts
- **DEFAULT** null (no system prompt)

### Requirement: Server Configuration

The harness SHALL support multiple server connection types.

#### Scenario: stdio server
- **GIVEN** server with `type: stdio`
- **WHEN** the harness connects
- **THEN** it SHALL spawn the command with args and env
- **AND** communicate via stdin/stdout

#### Scenario: http server
- **GIVEN** server with `type: http`
- **WHEN** the harness connects
- **THEN** it SHALL connect to the URL with optional headers

#### Scenario: Server timeout override
- **GIVEN** server with `timeout: 30`
- **WHEN** the harness connects
- **THEN** it SHALL use 30 seconds as connection timeout

#### Scenario: Subprocess environment for stdio
- **GIVEN** a stdio server with env section
- **WHEN** the subprocess is spawned
- **THEN** it SHALL inherit only `PATH` from host
- **AND** add explicit env values from config
- **AND** `${VAR}` in env values expands from bench-secrets.yaml first, then os.environ

### Requirement: Named Evaluators

The harness SHALL support reusable named evaluators.

#### Scenario: Define named evaluator
- **GIVEN** configuration with `evaluators.my_eval: {...}`
- **WHEN** tasks reference `evaluate: my_eval`
- **THEN** they SHALL use the named evaluator configuration

#### Scenario: Inline evaluator
- **GIVEN** task with inline `evaluate: { expected: "value" }`
- **WHEN** the task is evaluated
- **THEN** it SHALL use the inline configuration

### Requirement: Deterministic Evaluation

The harness SHALL support deterministic response matching.

#### Scenario: Expected string match
- **GIVEN** `evaluate.expected: "exact value"`
- **WHEN** the response is evaluated
- **THEN** it SHALL pass if the response contains the exact string

#### Scenario: Expected number match
- **GIVEN** `evaluate.expected: 42`
- **WHEN** the response is evaluated
- **THEN** it SHALL pass if the response contains the number

#### Scenario: Expected list (any match)
- **GIVEN** `evaluate.expected: ["a", "b"]`
- **WHEN** the response is evaluated
- **THEN** it SHALL pass if ALL expected values are found in the response

#### Scenario: Regex match
- **GIVEN** `evaluate.expected: [{regex: "pattern"}]`
- **WHEN** the response is evaluated
- **THEN** it SHALL pass if the regex matches somewhere in the response

#### Scenario: Expect error
- **GIVEN** `evaluate.expect_error: true`
- **WHEN** a task results in an error (e.g., timeout)
- **THEN** the error message SHALL be used as the response for evaluation
- **AND** evaluation proceeds normally against the error text
- **USE CASE** Testing timeout behavior or expected failure scenarios

### Requirement: LLM-as-Judge Evaluation

The harness SHALL support LLM-based evaluation.

#### Scenario: LLM evaluation prompt
- **GIVEN** `evaluate.prompt: "Is {response} correct? Expected: {expected}"`
- **WHEN** the response is evaluated
- **THEN** it SHALL call the LLM with the formatted prompt

#### Scenario: LLM evaluation model
- **GIVEN** `evaluate.model: openai/gpt-5-mini`
- **WHEN** LLM evaluation runs
- **THEN** it SHALL use the specified model
- **REQUIRED** No default - must be explicitly configured in evaluator

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
- **GIVEN** a benchmark file at `demo/bench/tool_<tool-name>.yaml`
- **WHEN** `ot-bench run demo/bench/tool_<tool-name>.yaml` is executed
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

### Requirement: OneTool Features Benchmark

The harness SHALL support a features benchmark (`features.yaml`) that tests OneTool-specific capabilities requiring LLM interpretation.

#### Scenario: Test alias resolution
- **GIVEN** a features benchmark with alias tests
- **WHEN** the benchmark runs
- **THEN** it SHALL verify the LLM correctly resolves aliases to functions
- **USE CASE** Tests that `$search q="foo"` expands correctly

#### Scenario: Test snippet expansion
- **GIVEN** a features benchmark with snippet tests
- **WHEN** the benchmark runs
- **THEN** it SHALL verify snippet expansion with variable substitution
- **USE CASE** Tests that `$snippet param=val` expands correctly

#### Scenario: Test proxy functionality
- **GIVEN** a features benchmark with proxy tests
- **WHEN** the benchmark runs with a configured proxy server
- **THEN** it SHALL verify tools from proxied servers are accessible

#### Scenario: Test OT server tools
- **GIVEN** a features benchmark with OT tool tests
- **WHEN** the benchmark runs
- **THEN** it SHALL verify list tools, get config, health check, and push operations

#### Scenario: Features excluded from benchmark
- **GIVEN** the features benchmark
- **WHEN** it defines tasks
- **THEN** it SHALL NOT include:
  - Prefix form tests (`__ot`, `__onetool__run`, etc.) - unit tested
  - Style form tests (inline, backticks, fence) - unit tested
  - Python construct tests (loops, conditionals) - unit tested
- **REASON** These test the executor, not LLM behaviour

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
- **GIVEN** a comparison benchmark (`compare.yaml`, `tools/*.yaml`)
- **WHEN** it defines defaults
- **THEN** it SHALL use NO system prompt
- **REASON** Simulates realistic real-world MCP vs OneTool comparison

#### Scenario: Testing benchmark system prompt
- **GIVEN** a testing benchmark (`features.yaml`, `python-exec.yaml`)
- **WHEN** it defines defaults
- **THEN** it SHALL use a simple system prompt:
  - "Execute code and return results. Never retry successful calls."

#### Scenario: Standard invocation format
- **GIVEN** a benchmark task (except invocation method tests)
- **WHEN** invoking OneTool
- **THEN** it SHALL use `__ot` + code fence format
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
  - Tool: `brave`, `context7`, `web-fetch`, `package`, `page-view`, `code-search`, `transform`
  - Feature: `invoke`, `proxy`, `snippet`, `direct`, `harness`
  - Execution: `parse`, `var`, `loop`, `if`, `comp`, `import`, `return`

### Requirement: Secrets-Only Variable Expansion

The harness SHALL expand `${VAR}` patterns in configuration using bench-secrets.yaml only.

#### Scenario: Variable in secrets
- **GIVEN** `${API_KEY}` in a config value
- **AND** `API_KEY: "secret123"` in bench-secrets.yaml
- **WHEN** configuration is loaded
- **THEN** the value SHALL be expanded to "secret123"

#### Scenario: Variable not in secrets
- **GIVEN** `${UNKNOWN_VAR}` in a config value
- **AND** UNKNOWN_VAR not in bench-secrets.yaml
- **WHEN** configuration is loaded
- **THEN** it SHALL raise an error
- **AND** message SHALL indicate the missing variable and suggest bench-secrets.yaml

#### Scenario: No os.environ fallback
- **GIVEN** `${MY_VAR}` in a header or url
- **AND** MY_VAR set in os.environ but NOT in bench-secrets.yaml
- **WHEN** configuration is loaded
- **THEN** os.environ value SHALL NOT be used
- **AND** error SHALL be raised

### Requirement: Header Validation

The harness SHALL validate that all headers are fully expanded before use.

#### Scenario: Unexpanded variable in header
- **GIVEN** a header value containing `${VAR}` after expansion
- **WHEN** the harness prepares the HTTP request
- **THEN** it SHALL raise an error
- **AND** message SHALL indicate the unexpanded variable
- **AND** suggest adding to bench-secrets.yaml

#### Scenario: All headers expanded
- **GIVEN** all `${VAR}` patterns resolved from bench-secrets.yaml
- **WHEN** the harness prepares the HTTP request
- **THEN** headers SHALL be used normally

### Requirement: Subprocess Environment Restriction

The harness SHALL restrict subprocess environment inheritance.

#### Scenario: Minimal environment inheritance
- **GIVEN** a stdio server configuration
- **WHEN** the subprocess is spawned
- **THEN** it SHALL start with only `PATH` from os.environ
- **AND** NOT inherit other environment variables

#### Scenario: Explicit environment variables
- **GIVEN** stdio server with:
  ```yaml
  env:
    MY_VAR: value
    API_KEY: ${API_KEY}
  ```
- **WHEN** the subprocess is spawned
- **THEN** MY_VAR and API_KEY SHALL be set in subprocess
- **AND** no other variables from host (except PATH)

#### Scenario: Pass-through variables
- **GIVEN** stdio server with `env: { HOME: ${HOME} }`
- **WHEN** the subprocess is spawned
- **THEN** `${HOME}` SHALL read from bench-secrets.yaml first
- **AND** fall back to os.environ for pass-through

### Requirement: Python Execution Testing

The execution engine SHALL be tested via unit tests, not benchmarks.

#### Scenario: Unit test coverage
- **GIVEN** the Python execution engine
- **WHEN** testing parsing, execution, return values, imports, and errors
- **THEN** tests SHALL be in `tests/unit/test_python_exec.py`
- **AND** tests SHALL use the `executor` fixture for direct execution
- **NOT** require LLM involvement

#### Scenario: No python_exec benchmark
- **GIVEN** the benchmark suite
- **WHEN** looking for execution engine tests
- **THEN** there SHALL NOT be a `python_exec.yaml` benchmark file
- **REASON** Execution tests are deterministic and don't need LLM

---

### Requirement: Per-LLM-Call Metrics

The harness SHALL track metrics for each individual LLM API call within a task execution.

#### Scenario: Track per-call input tokens
- **GIVEN** a task that makes multiple LLM calls (agentic loop)
- **WHEN** the task completes
- **THEN** `TaskResult.llm_call_metrics` SHALL contain one entry per LLM call
- **AND** each entry SHALL include `input_tokens` from that call's `response.usage.prompt_tokens`

#### Scenario: Track per-call output tokens
- **GIVEN** a task with multiple LLM calls
- **WHEN** the task completes
- **THEN** each `LLMCallMetrics` entry SHALL include `output_tokens` from `response.usage.completion_tokens`

#### Scenario: Track per-call latency
- **GIVEN** a task with multiple LLM calls
- **WHEN** each LLM API call is made
- **THEN** the harness SHALL measure wall-clock time for that call
- **AND** store it as `latency_ms` in the metrics entry

#### Scenario: Track cumulative input
- **GIVEN** a task with N LLM calls
- **WHEN** the task completes
- **THEN** each `LLMCallMetrics` entry SHALL include `cumulative_input`
- **AND** `cumulative_input` for call N equals sum of `input_tokens` for calls 1 through N
- **NOTE** This is a running total computed during execution, not stored redundantly

#### Scenario: Track tool calls per LLM response
- **GIVEN** an LLM response with tool calls
- **WHEN** metrics are recorded
- **THEN** `tool_calls_made` SHALL equal the number of tool calls in that response

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

### Requirement: Context Growth Analysis

The harness SHALL provide analysis of context growth patterns.

#### Scenario: Estimate base context
- **GIVEN** a completed task with per-call metrics
- **WHEN** `TaskResult.base_context` is accessed
- **THEN** it SHALL return the `input_tokens` from the first LLM call
- **REASON** First call represents system prompt + tool definitions before conversation history

#### Scenario: Calculate average context growth
- **GIVEN** a completed task with N > 1 LLM calls
- **WHEN** `TaskResult.context_growth_avg` is accessed
- **THEN** it SHALL return the average increase in `input_tokens` between consecutive calls
- **FORMULA** `sum(call[i+1].input_tokens - call[i].input_tokens) / (N - 1)`

#### Scenario: Handle single LLM call growth
- **GIVEN** a completed task with exactly 1 LLM call
- **WHEN** `TaskResult.context_growth_avg` is accessed
- **THEN** it SHALL return 0

### Requirement: CSV Results Export

The harness SHALL support exporting detailed results to CSV format.

#### Scenario: Enable CSV export
- **GIVEN** user runs `ot-bench run <file> --csv`
- **WHEN** the benchmark completes
- **THEN** results SHALL be written to `tmp/result-{timestamp}.csv`
- **AND** timestamp format SHALL be `YYYYMMDD-HHMM`

#### Scenario: Include task summary in CSV
- **GIVEN** CSV export is enabled
- **WHEN** results are written
- **THEN** each row SHALL include: `scenario`, `task`, `model`, `server`, `result`, `total_input`, `total_output`, `llm_calls`, `tool_calls`, `duration_s`, `cost_usd`

#### Scenario: Include context analysis in CSV
- **GIVEN** CSV export is enabled
- **WHEN** results are written
- **THEN** columns SHALL include `base_context` and `context_growth_avg`

#### Scenario: Create CSV directory automatically
- **GIVEN** CSV export is enabled
- **AND** `tmp/` directory does not exist
- **WHEN** results are written
- **THEN** the directory SHALL be created automatically

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

### Requirement: TUI Favorites Mode

The harness CLI SHALL support an interactive TUI mode for selecting benchmark files from favorites.

#### Scenario: Launch TUI mode

- **WHEN** user runs `ot-bench run --tui`
- **THEN** an interactive picker displays configured favorites
- **AND** user can select a benchmark to run

#### Scenario: Favorite file selection

- **GIVEN** a favorite with `path` pointing to a YAML file
- **WHEN** user selects that favorite
- **THEN** the benchmark runs with that file

#### Scenario: Favorite directory selection

- **GIVEN** a favorite with `path` pointing to a directory
- **WHEN** user selects that favorite
- **THEN** a sub-picker displays all YAML files in that directory
- **AND** user can select a specific file to run

#### Scenario: Directory scanning rules

- **GIVEN** a favorite directory is selected
- **WHEN** scanning for files
- **THEN** it recursively finds `*.yaml` and `*.yml` files
- **AND** excludes hidden directories (`.git`, `.venv`, etc.)
- **AND** displays relative paths in the picker

#### Scenario: Description from file metadata

- **GIVEN** a YAML benchmark file with a `description` field
- **WHEN** displaying in the picker
- **THEN** the description is shown alongside the name

#### Scenario: No favorites configured

- **GIVEN** no favorites in ot-bench.yaml
- **WHEN** user runs `ot-bench run --tui`
- **THEN** a message indicates no favorites are configured

### Requirement: Harness Configuration File

The harness CLI SHALL support a configuration file for CLI settings including favorites.

#### Scenario: Config file location

- **WHEN** no config path specified
- **THEN** looks for ot-bench.yaml in `config/` directory
- **OR** uses OT_BENCH_CONFIG environment variable

#### Scenario: Favorites configuration

- **GIVEN** a config file with favorites
- **WHEN** the CLI loads configuration
- **THEN** each favorite has:
  - `name`: Display name in picker (required)
  - `path`: File path or directory (required)

#### Scenario: Favorites config format

- **GIVEN** ot-bench.yaml
- **WHEN** favorites are defined
- **THEN** favorites are specified as:

  ```yaml
  favorites:
    - name: features
      path: demo/bench/features.yaml
    - name: all-bench
      path: demo/bench/
  ```
