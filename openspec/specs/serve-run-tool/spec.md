# serve-run-tool Specification

## Purpose

Defines the `run()` MCP tool for executing Python code with access to the tool registry. Handles code fence stripping, pack resolution, alias expansion, snippet processing, result capture, and error context.
## Requirements
### Requirement: Robust Fence Stripping

The system SHALL strip various code fence formats from commands.

#### Scenario: Triple backtick with language
- **GIVEN** command wrapped in ` ```python\ncode\n``` `
- **WHEN** run() processes the command
- **THEN** it SHALL extract only the code content

#### Scenario: Triple backtick without language
- **GIVEN** command wrapped in ` ```\ncode\n``` `
- **WHEN** run() processes the command
- **THEN** it SHALL extract only the code content

#### Scenario: Inline backticks
- **GIVEN** command wrapped in single backticks like `` `code` ``
- **WHEN** run() processes the command
- **THEN** it SHALL extract only the code content

#### Scenario: Nested fences preserved
- **GIVEN** code containing fence characters as data (not wrapping)
- **WHEN** run() processes the command
- **THEN** inner fence content SHALL be preserved

#### Scenario: No fences
- **GIVEN** command without any fence wrapping
- **WHEN** run() processes the command
- **THEN** it SHALL pass through unchanged

#### Scenario: Legacy prefix rejected
- **GIVEN** command `!onetool upper(text="hello")`
- **WHEN** run() processes the command
- **THEN** it SHALL return an error indicating invalid syntax

### Requirement: Unified Execution Path

The system SHALL use a single code path for all command execution.

#### Scenario: Simple function call
- **GIVEN** command like `search(query="test")`
- **WHEN** run() executes the command
- **THEN** it SHALL use the direct executor

#### Scenario: Python code block
- **GIVEN** multi-line Python code
- **WHEN** run() executes the command
- **THEN** it SHALL use the direct executor

### Requirement: Robust Result Capture

The system SHALL capture results from any valid Python expression or statement and serialize them consistently. Serialization SHALL degrade gracefully rather than reporting a successful tool call as an execution error, and SHALL always produce syntactically valid output for the requested format.

#### Scenario: Expression result
- **GIVEN** code that is a single expression like `search(query="test")`
- **WHEN** execution completes
- **THEN** the expression result SHALL be captured

#### Scenario: Last expression in block
- **GIVEN** multi-statement code where last statement is an expression
- **WHEN** execution completes
- **THEN** the last expression result SHALL be captured

#### Scenario: Explicit return
- **GIVEN** code with explicit `return value`
- **WHEN** execution completes
- **THEN** the returned value SHALL be captured

#### Scenario: No return value
- **GIVEN** code that has no return and last statement is not an expression
- **WHEN** execution completes
- **THEN** it SHALL return a success message indicating no value

#### Scenario: None return
- **GIVEN** code that explicitly returns None or function returns None
- **WHEN** execution completes
- **THEN** it SHALL indicate None was returned (not "no return value")

#### Scenario: Native dict serialization
- **GIVEN** a tool function that returns a Python dict
- **WHEN** the result is captured by the runner
- **THEN** the dict SHALL be serialized to compact JSON using `serialize_result()`
- **AND** the result SHALL NOT contain double-escaped JSON

#### Scenario: Native list serialization
- **GIVEN** a tool function that returns a Python list
- **WHEN** the result is captured by the runner
- **THEN** the list SHALL be serialized to compact JSON using `serialize_result()`
- **AND** the result SHALL NOT contain double-escaped JSON

#### Scenario: Discovery calls keep JSON default format
- **GIVEN** a discovery/introspection call (`ot.help`, `ot.tool_info`, `ot.tools`, `ot.packs`, `ot.pack_info`, `ot.servers`, `ot.aliases`, `ot.snippets`, `ot.snippet_info`, `ot.skills`)
- **AND** no explicit `__format__` is set in the executed code
- **WHEN** the result is captured by the runner
- **THEN** the runner SHALL default to compact JSON (`json`)
- **AND** explicit `__format__` SHALL still override this default

#### Scenario: String passthrough
- **GIVEN** a tool function that returns a plain string
- **WHEN** the result is captured by the runner
- **THEN** the string SHALL be returned as-is without additional serialization

#### Scenario: Composed tool results
- **GIVEN** code like `{"status": ot.status(), "config": ot.config()}`
- **WHEN** each tool returns a native dict
- **THEN** the composed result SHALL be a single clean JSON object
- **AND** nested values SHALL NOT be double-escaped strings

#### Scenario: Non-JSON-native values degrade instead of erroring
- **GIVEN** a tool result containing a value `json.dumps` cannot natively serialize (e.g. `datetime`, `Decimal`, `set`, `bytes`, `Path`, or a custom object), whether at the top level of the result or nested inside a dict/list
- **WHEN** the result is serialized
- **THEN** the value SHALL be degraded to its string representation
- **AND** the overall call SHALL be reported as successful (`isError:false`), not as an execution error
- **AND** the degrade behavior SHALL be identical regardless of whether the value is at the top level or nested

#### Scenario: NaN and Infinity degrade to valid JSON
- **GIVEN** a tool result containing `float('nan')`, `float('inf')`, or `float('-inf')`
- **WHEN** the result is serialized as JSON (`json` or `json_h` format)
- **THEN** the output SHALL be valid JSON parseable by a standard JSON parser
- **AND** it SHALL NOT contain the bare tokens `NaN`, `Infinity`, or `-Infinity`

#### Scenario: Lone surrogate does not crash serialization
- **GIVEN** a tool result string containing a lone UTF-16 surrogate code point (e.g. from `os.fsdecode`/`surrogateescape` handling of a filesystem name that is not valid UTF-8)
- **WHEN** the result is serialized and measured for size
- **THEN** it SHALL NOT raise `UnicodeEncodeError`
- **AND** the tool's actual output SHALL be returned to the caller (not replaced with a codec error message)

#### Scenario: YAML formats never emit unsafe tags
- **GIVEN** a tool result containing any Python value, including ones not natively representable by the default YAML dumper
- **WHEN** the result is serialized with `__format__` set to `yml` or `yml_h`
- **THEN** the output SHALL NOT contain Python-specific YAML tags such as `!!python/object` or `!!set`
- **AND** unrepresentable values SHALL degrade to a plain-YAML-compatible representation rather than raising an error

#### Scenario: Result format label matches the format actually produced
- **GIVEN** a top-level result value that is not natively JSON-serializable (e.g. a `set` or `datetime` returned directly, not nested in a dict/list)
- **WHEN** the result is serialized
- **THEN** the reported `format` SHALL accurately reflect the format that was actually produced for that value

### Requirement: Indentation-Safe Code Wrapping

The system SHALL correctly wrap code regardless of indentation.

#### Scenario: Already indented code
- **GIVEN** code that is already indented (e.g., from LLM response)
- **WHEN** wrapped for execution
- **THEN** indentation SHALL be normalized correctly

#### Scenario: Mixed indentation
- **GIVEN** code with mixed tabs and spaces
- **WHEN** wrapped for execution
- **THEN** it SHALL handle or normalize the indentation

#### Scenario: Empty lines
- **GIVEN** code with empty lines between statements
- **WHEN** wrapped for execution
- **THEN** empty lines SHALL not cause indentation errors

### Requirement: Error Context

The system SHALL provide clear error context for failures.

#### Scenario: Syntax error location
- **GIVEN** code with syntax error
- **WHEN** execution fails
- **THEN** error SHALL include line number in original code (not wrapped)

#### Scenario: Runtime error context
- **GIVEN** code that raises exception during execution
- **WHEN** execution fails
- **THEN** error SHALL include the exception type and message

#### Scenario: Tool not found
- **GIVEN** command calling non-existent tool
- **WHEN** execution fails
- **THEN** error SHALL list available tools

#### Scenario: Argument error
- **GIVEN** tool called with wrong arguments
- **WHEN** execution fails
- **THEN** error SHALL include expected signature

### Requirement: Pack Resolution

The system SHALL resolve dot-notation packs to actual tool functions.

#### Scenario: Simple pack call
- **GIVEN** command `brave.web_search(query="test")` where `brave` pack contains `web_search`
- **WHEN** run() processes the command
- **THEN** it SHALL call the `web_search` function from `brave` pack

#### Scenario: Unknown pack
- **GIVEN** command `unknown.func()` where `unknown` pack does not exist
- **WHEN** run() processes the command
- **THEN** it SHALL return error listing available packs

#### Scenario: Function not in pack
- **GIVEN** command `brave.nonexistent()` where function does not exist in `brave` pack
- **WHEN** run() processes the command
- **THEN** it SHALL return error listing available functions in that pack

#### Scenario: Same function name in different packs
- **GIVEN** `brave.search()` and `context7.search()` exist as distinct functions
- **WHEN** run() processes `brave.search(query="test")`
- **THEN** it SHALL call the brave-specific search function

#### Scenario: Enabled proxy server pack available in same command
- **GIVEN** a configured proxy server pack `github` is initially disconnected
- **WHEN** code executes `ot_servers.enable(name="github")` then `github.search_repositories(query="tooling")` in the same run() command
- **THEN** the `github` pack SHALL be available for immediate resolution in that same command

#### Scenario: Nested ot pack access rejected with direct syntax hint
- **GIVEN** a pack named `ground` exists
- **WHEN** code attempts `ot.ground.search(query="test")`
- **THEN** execution SHALL fail with a message directing callers to use direct pack syntax such as `ground.search(...)`

### Requirement: Alias Resolution

The system SHALL resolve configured aliases to their target functions.

#### Scenario: Simple alias
- **GIVEN** alias `ws` configured to map to `brave.web_search`
- **WHEN** command `ws(query="test")` is processed
- **THEN** it SHALL execute as `brave.web_search(query="test")`

#### Scenario: Unknown alias passthrough
- **GIVEN** command `unknown(arg=val)` where `unknown` is not a configured alias
- **WHEN** run() processes the command
- **THEN** it SHALL attempt to execute `unknown(arg=val)` directly

### Requirement: Snippet Expansion

The system SHALL expand snippet templates using Jinja2.

#### Scenario: Snippet invocation
- **GIVEN** command `:wsq q1=AI q2=ML p=Compare` where `wsq` snippet is configured
- **WHEN** run() processes the command
- **THEN** it SHALL expand the snippet template and execute the result

#### Scenario: Snippet expansion inside multiline python workflow
- **GIVEN** a multiline run() command with normal python statements and `result = __onetool(":wsq q1=AI q2=ML p=Compare")`
- **WHEN** run() executes the command
- **THEN** `__onetool(...)` SHALL expand and execute the snippet command and return its tool result to the caller

#### Scenario: Nested execution does not leak magics into the outer result
- **GIVEN** a multiline run() command that sets `__format__ = 'json_h'` at the outer level and also calls `__onetool("code_that_sets___format__ = 'raw'")` as a nested command
- **WHEN** the outer command's result is captured
- **THEN** the outer command's `__format__` (`'json_h'`) SHALL be used to serialize the outer result
- **AND** the nested command's `__format__` setting SHALL NOT overwrite the outer command's setting
- **AND** the same isolation SHALL apply to `__sanitize__` and `__force_context__`

#### Scenario: Nested execution does not leak ordinary variables
- **GIVEN** a nested `__onetool(...)` command that assigns to a variable name also used by the outer command
- **WHEN** the outer command continues execution after the nested call returns
- **THEN** the outer command's variable value SHALL be unaffected by the nested command's assignment

#### Scenario: Nested execution recursion is bounded
- **GIVEN** a command that triggers recursive `__onetool(...)` calls (directly, or via a snippet expanding to another `__onetool(...)` call) beyond a small fixed depth limit
- **WHEN** the nested depth limit is exceeded
- **THEN** the system SHALL raise a clear error identifying the depth limit
- **AND** it SHALL NOT allow an unbounded recursion to raise `RecursionError`

#### Scenario: Nested execution error lines are mapped to the nested command
- **GIVEN** a nested `__onetool(...)` command whose code raises an exception on a specific line of the nested command's source
- **WHEN** the error is reported
- **THEN** the reported line number SHALL correspond to the nested command's source, not the outer command's line offset

### Requirement: Project Pack Proxy

The `proj` pack SHALL use a special proxy supporting dynamic project attributes.

#### Scenario: Dynamic attribute resolution
- **GIVEN** `projects: { onetool: ~/projects/onetool }` in config
- **WHEN** code containing `proj.onetool` is executed
- **THEN** it SHALL resolve to the configured project path as `ProjectPath`

#### Scenario: Function priority
- **GIVEN** the `proj` pack has `path` and `list` functions
- **WHEN** `proj.path` or `proj.list` is accessed
- **THEN** the function SHALL be returned, not a project lookup

#### Scenario: Path operations in code
- **GIVEN** `projects: { onetool: ~/projects/onetool }` in config
- **WHEN** code containing `proj.onetool / "src"` is executed
- **THEN** it SHALL evaluate to the joined path as `ProjectPath`

#### Scenario: Error message for unknown project
- **GIVEN** `projects: { onetool: ~/projects/onetool }` in config
- **WHEN** code containing `proj.unknown` is executed
- **THEN** it SHALL raise `AttributeError` with message listing:
  - Available functions (path, list)
  - Available projects (onetool)

### Requirement: Parameter Prefix Matching

The system SHALL resolve abbreviated parameter names to full parameter names using prefix matching. The system SHALL refuse to silently resolve two distinct provided arguments to the same target parameter.

#### Scenario: Exact parameter match
- **GIVEN** a tool function with parameter `query`
- **WHEN** called with `query="test"`
- **THEN** the parameter SHALL be passed through unchanged

#### Scenario: Single prefix match
- **GIVEN** a tool function with parameter `query`
- **WHEN** called with `q="test"`
- **THEN** the parameter SHALL resolve to `query="test"`

#### Scenario: Multiple prefix matches with first-wins
- **GIVEN** a tool function with parameters `query_info`, `query`, `quality` (in that order)
- **WHEN** called with `q="test"`
- **THEN** the parameter SHALL resolve to `query_info="test"` (first in signature order)

#### Scenario: Partial prefix match
- **GIVEN** a tool function with parameters `query_info`, `query`, `quality`
- **WHEN** called with `qual="test"`
- **THEN** the parameter SHALL resolve to `quality="test"` (only match)

#### Scenario: No match passthrough
- **GIVEN** a tool function with parameter `query`
- **WHEN** called with `xyz="test"`
- **THEN** the parameter SHALL be passed through unchanged
- **AND** the underlying function SHALL raise its normal error for unknown parameter

#### Scenario: Mixed exact and prefix parameters
- **GIVEN** a tool function with parameters `query`, `count`
- **WHEN** called with `query="test", c=5`
- **THEN** the parameters SHALL resolve to `query="test", count=5`

#### Scenario: Exact match and colliding prefix match raise an ambiguity error
- **GIVEN** a tool function with parameter `query`
- **WHEN** called with `query="real", q="typo"` (an exact match for `query` and a separate key `q` that prefix-matches `query`)
- **THEN** the system SHALL raise a clear ambiguity error naming both `query` and `q` and the shared target `query`
- **AND** it SHALL NOT silently resolve to either `query="real"` or `query="typo"`

#### Scenario: Two prefix matches colliding on the same target raise an ambiguity error
- **GIVEN** a tool function with parameter `count`
- **WHEN** called with `c="A", count="B"` (both keys resolve to the target `count`)
- **THEN** the system SHALL raise a clear ambiguity error
- **AND** the result SHALL NOT depend on the order the keyword arguments were provided

### Requirement: Prefix Matching Scope

Parameter prefix matching SHALL apply to all tool execution paths.

#### Scenario: Internal tool prefix matching
- **GIVEN** a bundled in-process tool
- **WHEN** called with abbreviated parameter names
- **THEN** prefix matching SHALL be applied

#### Scenario: Extension tool prefix matching
- **GIVEN** a configured in-process extension tool
- **WHEN** called with abbreviated parameter names
- **THEN** prefix matching SHALL be applied

#### Scenario: MCP proxy tool prefix matching
- **GIVEN** an MCP proxy tool
- **WHEN** called with abbreviated parameter names
- **THEN** prefix matching SHALL be applied using the tool's input schema

#### Scenario: ot pack tool prefix matching
- **GIVEN** an ot pack introspection tool (e.g., `ot.tools`, `ot.help`)
- **WHEN** called with abbreviated parameter names (e.g., `p="fire"` for `pattern`)
- **THEN** prefix matching SHALL be applied
- **AND** the abbreviated parameter SHALL resolve to the full parameter name

### Requirement: Output Format Control

The system SHALL support a `__format__` magic variable to control result serialisation.

#### Scenario: Default format (compact JSON)
- **GIVEN** code that returns a dict without setting `__format__`
- **WHEN** the result is serialised
- **THEN** it SHALL use compact JSON with no whitespace

#### Scenario: Explicit json format
- **GIVEN** code that sets `__format__ = "json"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use compact JSON (same as default)

#### Scenario: Human-readable JSON format
- **GIVEN** code that sets `__format__ = "json_h"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use JSON with 2-space indentation

#### Scenario: YAML flow format
- **GIVEN** code that sets `__format__ = "yml"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use YAML flow style (inline collections)

#### Scenario: Human-readable YAML format
- **GIVEN** code that sets `__format__ = "yml_h"` and returns a dict
- **WHEN** the result is serialised
- **THEN** it SHALL use YAML block style with proper indentation

#### Scenario: Raw format
- **GIVEN** code that sets `__format__ = "raw"` and returns any value
- **WHEN** the result is serialised
- **THEN** it SHALL use Python `str()` conversion

#### Scenario: String passthrough unchanged
- **GIVEN** code that returns a string (regardless of `__format__` setting)
- **WHEN** the result is serialised
- **THEN** the string SHALL be returned unchanged

#### Scenario: Invalid format ignored
- **GIVEN** code that sets `__format__` to an unknown value
- **WHEN** the result is serialised
- **THEN** it SHALL fall back to default compact JSON

### Requirement: Sanitisation Magic Variable

The system SHALL support a `__sanitize__` magic variable to control output sanitisation.

#### Scenario: Explicit enable
- **GIVEN** code that sets `__sanitize__ = True`
- **WHEN** the result is returned
- **THEN** sanitisation SHALL be applied with boundary wrapping

#### Scenario: Explicit disable
- **GIVEN** code that sets `__sanitize__ = False`
- **WHEN** the result is returned
- **THEN** sanitisation SHALL NOT be applied

#### Scenario: Default behaviour
- **GIVEN** code that does not set `__sanitize__`
- **WHEN** the result is returned
- **THEN** sanitisation SHALL NOT be applied (opt-in)

### Requirement: Large Output Handling

The system SHALL intercept tool outputs exceeding a configurable size threshold and store them to disk. The system SHALL also store outputs unconditionally when `__force_context__` is set to `True`. Stored content SHALL receive the same sanitization treatment as inline content, and SHALL preserve the caller's requested output format.

#### Scenario: Output below threshold
- **GIVEN** `output.max_inline_size` is configured to 5000 bytes
- **WHEN** a tool returns output of 1000 bytes
- **THEN** the output SHALL be returned inline unchanged

#### Scenario: Output exceeds threshold
- **GIVEN** `output.max_inline_size` is configured to 5000 bytes
- **WHEN** a tool returns output of 20000 bytes
- **THEN** the output SHALL be stored through the configured result-store backend
- **AND** a summary dict SHALL be returned instead of full content

#### Scenario: output policy hook exempts ot.result from large output gate
- **GIVEN** `output.max_inline_size` is configured to any positive value
- **WHEN** the tool being executed is `ot.result`
- **THEN** the output SHALL be returned inline regardless of size
- **AND** the output SHALL NOT be stored or re-wrapped into a second handle

#### Scenario: output policy hook exempts ctx tools from large output gate
- **GIVEN** `output.max_inline_size` is configured to any positive value
- **WHEN** the tool being executed has a canonical or alias ctx name
- **THEN** the output SHALL be returned inline regardless of size
- **AND** the output SHALL NOT be stored or re-wrapped into a second handle

#### Scenario: output policy hook exempts discovery tools from large output gate
- **GIVEN** `output.max_inline_size` is configured to any positive value
- **WHEN** the tool being executed is `ot.help` or `ot.tool_info`
- **THEN** the output SHALL be returned inline regardless of size
- **AND** the output SHALL NOT be stored or re-wrapped into a second handle

#### Scenario: __force_context__ overrides size threshold
- **GIVEN** code sets `__force_context__ = True`
- **AND** the output is smaller than `output.max_inline_size`
- **WHEN** the result is returned
- **THEN** the output SHALL be stored through the configured result-store backend
- **AND** a summary dict SHALL be returned instead of inline output

#### Scenario: Summary response format
- **GIVEN** a large output is stored by the default ctx result-store backend
- **WHEN** the summary is returned
- **THEN** it SHALL include:
  - `handle`: Unique identifier for querying
  - `total_lines`: Line count of stored content
  - `size_bytes`: Size of stored content
  - `content_type`: Stored content type
  - `preview`: First N lines (configurable via `output.preview_lines`)
  - `status`: Handle availability state
  - `next_commands`: Ordered follow-up commands:
    - `ctx.toc(handle='...')`
    - `ctx.ask(handle='...', q='...')`
    - `ctx.read(handle='...', limit=80)`

#### Scenario: Content file created
- **GIVEN** a large output is stored
- **WHEN** storage completes
- **THEN** the file SHALL be stored as `result-{guid}.txt`

#### Scenario: Meta file created
- **GIVEN** a large output is stored
- **WHEN** storage completes
- **THEN** a meta file `result-{guid}.meta.json` SHALL be created
- **AND** meta file SHALL contain: `handle`, `total_lines`, `size_bytes`, `created_at`, `tool`

#### Scenario: Deflected content is sanitized before or at read
- **GIVEN** a large output containing content that would be sanitized if returned inline (e.g. a trigger pattern)
- **WHEN** the output is deflected to a stored handle
- **THEN** the sanitized form SHALL be what is returned via `ctx.read(handle=...)` (either by sanitizing before store, or by sanitizing at read time)
- **AND** the raw unsanitized body SHALL NOT be retrievable through the normal `ctx.read` path

#### Scenario: Deflected content preserves the requested output format
- **GIVEN** code sets `__format__ = 'yml'` (or any non-default format) and produces output large enough to be deflected
- **WHEN** the output is stored and later read via `ctx.read(handle=...)`
- **THEN** the stored content SHALL be serialized using the requested format, not silently re-serialized as JSON

### Requirement: Result Store Cleanup

The system SHALL automatically clean up expired result files.

#### Scenario: TTL-based expiry
- **GIVEN** `output.result_ttl` is configured to 3600 seconds
- **WHEN** a result file is older than TTL
- **THEN** it SHALL be eligible for cleanup

#### Scenario: Cleanup on store
- **GIVEN** expired result files exist
- **WHEN** a new large output is stored
- **THEN** expired files SHALL be cleaned up

### Requirement: Command Normalization Resilience

The system SHALL NOT allow command normalization (fence stripping, AST unparse, quote-style rewriting) to raise an uncaught exception out of the `run` tool handler. Any string argument, including one containing both an apostrophe and a newline, SHALL execute successfully.

#### Scenario: Apostrophe and newline in a string argument
- **GIVEN** command `note(text="Here's the plan:\nstep 1")` (a double-quoted string containing both an apostrophe and a literal newline)
- **WHEN** run() prepares and executes the command
- **THEN** it SHALL execute successfully
- **AND** it SHALL NOT raise `SyntaxError` or any other uncaught exception during preparation

#### Scenario: Quote-rewriting skips control characters
- **GIVEN** a double-quoted string literal containing a newline, carriage return, or other control character (ord < 0x20)
- **WHEN** the normalizer considers rewriting it to single-quoted form
- **THEN** it SHALL leave that token unchanged rather than re-quoting it
- **AND** the surrounding code SHALL remain valid, parseable Python

#### Scenario: Normalization failure falls back to unnormalized code
- **GIVEN** the normalization step raises any exception for any reason
- **WHEN** `prepare_command` runs
- **THEN** it SHALL catch the exception and fall back to the validated-but-unnormalized code
- **AND** SHALL NOT propagate the exception to the caller

#### Scenario: Preparation failure never escapes the run handler
- **GIVEN** `prepare_command` raises an unanticipated exception for any reason
- **WHEN** the `run` tool handler calls `prepare_command`
- **THEN** it SHALL catch the exception and produce a clean, actionable error result
- **AND** SHALL NOT let the exception propagate uncaught out of the tool handler

### Requirement: MCP Error Signaling

The `run` tool SHALL signal execution failure via the MCP `isError` protocol field so that a client or agent branching on `isError` can reliably distinguish success from failure. Because the installed FastMCP version sets `isError` exclusively by raising `fastmcp.exceptions.ToolError` (a returned `ToolResult` always yields `isError:false`), the system SHALL raise `ToolError` for every failure path.

#### Scenario: Validation failure yields isError:true
- **GIVEN** a command that fails preparation validation (e.g. references an unknown pack)
- **WHEN** `run()` processes the command
- **THEN** the MCP response SHALL have `isError:true`
- **AND** the response text SHALL contain the actionable validation error message

#### Scenario: User-code exception yields isError:true
- **GIVEN** a command whose execution raises a runtime exception (e.g. a `KeyError`)
- **WHEN** `run()` executes the command
- **THEN** the MCP response SHALL have `isError:true`
- **AND** the response text SHALL contain the error message produced by execution

#### Scenario: Successful execution yields isError:false
- **GIVEN** a command that executes successfully and returns a value
- **WHEN** `run()` executes the command
- **THEN** the MCP response SHALL have `isError:false`
- **AND** the response text SHALL contain the serialized result

#### Scenario: Error text is preserved in the raised exception
- **GIVEN** any failure path (preparation error or execution error)
- **WHEN** `run()` raises `ToolError`
- **THEN** the exception message SHALL contain the same actionable error text that would previously have been returned in `ToolResult.content`

### Requirement: Non-Blocking Execution

The `run` tool SHALL execute user code off the FastMCP event-loop thread unconditionally, so that a blocking tool call cannot stall concurrent `run`/`ping`/cancellation processing regardless of whether any MCP proxy server is connected.

#### Scenario: Blocking tool does not stall concurrent requests
- **GIVEN** no MCP proxy servers are connected
- **AND** one `run()` call is executing a slow, blocking tool (e.g. a multi-second file read or network fetch)
- **WHEN** a second `run()` or `ping` request arrives concurrently
- **THEN** the second request SHALL be processed without waiting for the first to complete

#### Scenario: User code always runs via a thread offload
- **GIVEN** any command being executed, with or without connected proxy servers
- **WHEN** `run()` dispatches the command for execution
- **THEN** the execution SHALL be dispatched via a thread offload (not run synchronously on the event-loop thread)

### Requirement: Per-Tool Execution Timeout

The `run` tool SHALL enforce a soft caller timeout on user code, so that a hung
or excessively slow tool call returns a clean failure instead of holding that
caller indefinitely. Reaching the timeout SHALL stop waiting for the result but
SHALL NOT claim to terminate the underlying in-process Python thread. The
underlying execution MAY continue performing side effects after the timeout and
SHALL remain admitted and accounted for until it actually finishes.

#### Scenario: Execution exceeding the timeout fails cleanly

- **GIVEN** a command whose execution exceeds the per-tool timeout
- **WHEN** the timeout is reached
- **THEN** `run()` SHALL raise `ToolError` with a message indicating the caller timed out
- **AND** the message SHALL state that underlying in-process work may continue
- **AND** the underlying job SHALL remain admitted until its thread finishes

#### Scenario: Post-timeout side effect remains possible

- **GIVEN** a command blocks past its caller timeout and then performs a side effect
- **WHEN** the caller receives the timeout failure and the blocked command is released
- **THEN** the side effect MAY occur
- **AND** completion SHALL release the job's admission slot

#### Scenario: Execution within the timeout is unaffected

- **GIVEN** a command whose execution completes well within the configured per-tool timeout
- **WHEN** `run()` executes the command
- **THEN** it SHALL complete and return its result normally, with no timeout-related error

### Requirement: Bounded In-Process Execution Admission

OneTool SHALL admit at most eight in-process execution jobs per process. The
bound SHALL include running and queued underlying work across all callers and
event loops. A caller timeout or cancellation SHALL NOT release a slot; only
actual underlying thread completion SHALL release it. When all eight slots are
occupied, the next request SHALL fail immediately with an execution-capacity
error and SHALL NOT submit additional underlying work.

#### Scenario: Timed-out work fills capacity

- **GIVEN** eight admitted jobs have timed out for their callers but their underlying threads remain blocked
- **WHEN** a ninth execution request arrives
- **THEN** it SHALL fail immediately with an execution-capacity error
- **AND** no ninth underlying job SHALL be submitted or queued

#### Scenario: Underlying completion restores capacity

- **GIVEN** all eight slots are occupied by underlying jobs
- **WHEN** one underlying thread actually finishes
- **THEN** its slot SHALL be released
- **AND** a subsequent request SHALL be eligible for admission

#### Scenario: Caller cancellation does not release capacity

- **GIVEN** an admitted job is still running
- **WHEN** its awaiting caller is cancelled
- **THEN** the underlying job SHALL continue and remain counted
- **AND** overflow admission behavior SHALL remain unchanged until that job finishes

### Requirement: In-Process Execution Shutdown

MCP server shutdown SHALL stop accepting new in-process execution jobs and SHALL
wait for every admitted job, including work detached by caller timeout or
cancellation, to actually finish before dependent runtime resources are closed.
The runtime SHALL NOT claim hard termination of Python threads.

#### Scenario: Shutdown drains detached work

- **GIVEN** a caller has timed out while its admitted thread remains blocked
- **WHEN** MCP server shutdown begins
- **THEN** new execution admission SHALL be rejected
- **AND** shutdown SHALL remain pending until the blocked thread is released and finishes
- **AND** the admitted-work count SHALL then reach zero

#### Scenario: Startup reopens clean admission

- **GIVEN** a prior server lifespan completed shutdown with no admitted work
- **WHEN** a new MCP server lifespan starts in the same process
- **THEN** execution admission SHALL reopen with capacity eight

### Requirement: Empty Command Validation

The system SHALL treat an empty or whitespace-only command as an explicit validation error rather than silently reporting success.

#### Scenario: Empty command is rejected
- **GIVEN** command `""` or a command consisting only of whitespace
- **WHEN** `run()` processes the command
- **THEN** it SHALL return a preparation error indicating the command is empty
- **AND** the response SHALL have `isError:true` (per the MCP Error Signaling requirement)
- **AND** it SHALL NOT report `"Code executed successfully (no return value)"` or any other success message

### Requirement: Tool Annotations Reflect Risk

The `run` tool's MCP annotations SHALL reflect that it is a general-purpose surface capable of destructive operations (e.g. any registered tool, including `file.delete`), so that clients gating confirmation prompts on the `destructiveHint` annotation do not skip confirmation for a genuinely destructive call.

#### Scenario: destructiveHint is true
- **GIVEN** the `run` tool's registered MCP annotations
- **WHEN** a client inspects `destructiveHint`
- **THEN** it SHALL be `true`
