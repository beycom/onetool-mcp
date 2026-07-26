## MODIFIED Requirements

### Requirement: Unified Help

The `ot.help()` function SHALL provide deterministic unified help across tools, packs, configured
servers, snippets, aliases, and registered help topics. Its public keyword-only parameters SHALL
include `query`, `topic`, `info`, `ask`, and `answer_only`.

#### Scenario: General help (no query)
- **GIVEN** no query, topic, or ask parameter
- **WHEN** `ot.help()` is called
- **THEN** it SHALL return a compact deterministic overview with discovery commands, info levels, quick examples, usage tips, setup help, and proxy recovery
- **AND** it SHALL NOT call an LLM

#### Scenario: Ask mode with LLM available
- **GIVEN** `ask` is a non-empty question
- **AND** an OpenAI-compatible API key and model configuration are available
- **WHEN** `ot.help(ask="how do I search?")` is called
- **THEN** it SHALL append an LLM-generated answer grounded only in the deterministic help context selected by `query` and `topic`

#### Scenario: Ask mode unavailable
- **GIVEN** `ask` is a non-empty question
- **AND** the configured LLM is unavailable or fails
- **WHEN** `ot.help(ask="how do I search?")` is called
- **THEN** it SHALL still return the deterministic narrowed help context
- **AND** it SHALL include an explicit ask-unavailable message

#### Scenario: Answer-only ask mode
- **GIVEN** `ask` is non-empty and the configured LLM succeeds
- **WHEN** `ot.help(query="whiteboard", topic="dsl", ask="How do I connect grouped nodes?", answer_only=True)` is called
- **THEN** it SHALL return the grounded answer without repeating the full deterministic DSL context
- **AND** the answer SHALL use only the selected deterministic topic as evidence

#### Scenario: Answer-only ask fallback
- **GIVEN** `answer_only=True` and the configured LLM is unavailable or fails
- **WHEN** topic-scoped help is called with a non-empty `ask`
- **THEN** it SHALL return an explicit ask-unavailable message plus the narrowed deterministic help
- **AND** it SHALL NOT return an empty result

#### Scenario: Answer-only without a question
- **GIVEN** `answer_only=True` and `ask` is empty
- **WHEN** `ot.help()` is called
- **THEN** it SHALL raise `ValueError` explaining that `answer_only` requires `ask`

#### Scenario: Exact tool lookup
- **GIVEN** a query matching a tool name exactly, such as `brave.search`
- **WHEN** `ot.help(query="brave.search")` is called
- **THEN** it SHALL return the tool heading, description, signature, typed arguments, returns, example when available, and canonical documentation URL

#### Scenario: Exact configured server lookup
- **GIVEN** a query matching a configured MCP server name exactly
- **WHEN** `ot.help(query="chrome_devtools")` is called
- **THEN** it SHALL return server name, MCP proxy type, connection status, call-as name when different, authoritative source, tools when connected, and recovery when disconnected
- **AND** native MCP initialization instructions SHALL appear before maintained or user-configured instructions

#### Scenario: Exact pack lookup
- **GIVEN** a query matching a pack name or short pack alias exactly
- **WHEN** `ot.help(query="brave")` is called
- **THEN** it SHALL return pack heading, type, reviewed summary, available help topics, tool list, and canonical documentation URL
- **AND** pack instructions SHALL not merely duplicate the same one-line summary

#### Scenario: Topic-scoped pack resource
- **GIVEN** a pack registers a packaged help resource named `dsl`
- **WHEN** `ot.help(query="whiteboard", topic="dsl")` is called
- **THEN** it SHALL return that versioned resource content through the tool result
- **AND** it SHALL not require the caller to read a repository or server-local path

#### Scenario: Topic-scoped dynamic provider
- **GIVEN** a pack registers a read-only provider topic such as `policy`, `providers`, `templates`, `setup`, or `config`
- **WHEN** exact pack help requests that topic
- **THEN** the provider SHALL render current deterministic guidance from registered resources, active config, or live status
- **AND** requesting help SHALL NOT execute a mutating pack operation

#### Scenario: Unknown topic
- **GIVEN** an exact subject exists but the requested topic does not
- **WHEN** topic-scoped help is called
- **THEN** it SHALL return an error naming the unknown topic and listing valid topics for that subject

#### Scenario: Snippet lookup
- **GIVEN** a query starting with `:`, such as `:b_q`
- **WHEN** `ot.help(query=":b_q")` is called
- **THEN** it SHALL return snippet name, description, parameters with defaults, body template, and example invocation

#### Scenario: Alias lookup
- **GIVEN** a query matching a configured alias
- **WHEN** `ot.help(query="ws")` is called
- **THEN** it SHALL return alias name, target function, and a usage hint

#### Scenario: Fuzzy search
- **GIVEN** a query that has no exact subject match
- **WHEN** `ot.help(query="web fetch")` is called
- **THEN** it SHALL return ranked results grouped by tools, packs, snippets, aliases, configured servers, and help topics
- **AND** matching SHALL consider names and descriptions

#### Scenario: Direct run invocation help
- **GIVEN** a query for direct invocation syntax such as `__onetool`, `__ot`, `run`, `direct command`, or `snippet`
- **WHEN** `ot.help(query=...)` is called
- **THEN** it SHALL return deterministic guidance containing `__onetool <code>`, `__ot <code>`, `:snippet key=value`, direct `pack.tool(arg=value)`, and `ot.tool_info(name="pack.tool")`
- **AND** it SHALL state that colon syntax applies only to snippets
- **AND** it SHALL distinguish connected-agent MCP `run(command=...)` from the explicit `onetool direct` CLI workflow

#### Scenario: Fuzzy matching with typos
- **GIVEN** a query with a close typo
- **WHEN** `ot.help(query="scaffoldl")` is called
- **THEN** it SHALL find close subjects/topics and sort them by match score

#### Scenario: Info level min
- **GIVEN** `info="min"`
- **WHEN** fuzzy or list-style help is called
- **THEN** it SHALL return only matching names

#### Scenario: Info level default
- **GIVEN** no info parameter or `info="default"`
- **WHEN** help is called
- **THEN** it SHALL return names with brief descriptions or the default exact-subject overview

#### Scenario: Info level full
- **GIVEN** `info="full"`
- **WHEN** help is called
- **THEN** it SHALL include all available deterministic fields for the selected subject/topic

#### Scenario: Documentation URL generation
- **GIVEN** a local tool or pack has a reviewed `doc_slug`
- **WHEN** help is displayed
- **THEN** it SHALL include `https://onetool.beycom.online/reference/tools/{doc_slug}/`
- **AND** `doc_slug` SHALL equal the corresponding published reference-page filename
- **AND** catalog validation SHALL reject a missing page or slug mismatch instead of applying hard-coded URL overrides

#### Scenario: No matches
- **GIVEN** a query matches no subject or topic
- **WHEN** `ot.help(query="xyznonexistent")` is called
- **THEN** it SHALL state that no match was found
- **AND** it SHALL suggest browsing tools, packs, and configured servers

#### Scenario: No matches with proxy/server intent
- **GIVEN** a no-match query contains proxy/server intent
- **WHEN** `ot.help(query="proxy enable flow")` is called
- **THEN** fallback guidance SHALL include `ot.servers()`, `ot-mcp-proxy`, `ot_servers.enable(name="...")`, generic proxy setup help, and a direction to consult the target server's current authoritative MCP documentation

## ADDED Requirements

### Requirement: Read-only pack setup diagnostics

`ot.help(query="<pack>", topic="setup")` SHALL render a deterministic read-only readiness report
from the composed catalog, loaded registry, active config, normalized requirements, secret
presence, executable/library availability, and relevant proxy status.

#### Scenario: Pack is ready
- **GIVEN** a pack is installed and all active requirements are satisfied
- **WHEN** its setup topic is requested
- **THEN** the report SHALL identify the pack and install profile, show readiness as ready, list active requirements as satisfied, and provide a non-mutating verification call when one is registered

#### Scenario: Pack extra is absent
- **GIVEN** a cataloged pack belongs to an uninstalled optional extra
- **WHEN** exact setup help is requested
- **THEN** the report SHALL identify the missing OneTool extra and supported package install target
- **AND** it SHALL not run the package manager

#### Scenario: Pack has mixed requirement state
- **GIVEN** a pack has missing required dependencies plus inactive optional or conditional dependencies
- **WHEN** its setup topic is requested
- **THEN** required missing items SHALL be distinguished from optional/inactive items
- **AND** each item SHALL identify its kind and actionable next step

#### Scenario: Pack config is invalid
- **GIVEN** active `tools.<pack>` values fail the declared config model
- **WHEN** setup or config help is requested
- **THEN** the report SHALL identify the invalid field path and validation reason
- **AND** it SHALL show defaults and non-sensitive configured values where safe

#### Scenario: Setup diagnostics redact sensitive data
- **GIVEN** requirements or active config include secrets, bearer tokens, headers, environment values, or credential-like fields
- **WHEN** setup/config help is rendered
- **THEN** it SHALL expose only secret names and set/unset state
- **AND** it SHALL not expose expanded or literal secret values

### Requirement: Read-only proxy setup diagnostics

Runtime help SHALL diagnose configured servers and SHALL provide a generic MCP proxy setup topic
derived from `McpServerConfig` without mutating config or runtime state. It SHALL not maintain
server-specific setup presets.

#### Scenario: Generic proxy setup is requested
- **GIVEN** the target MCP server is not yet configured
- **WHEN** generic proxy setup help is requested
- **THEN** it SHALL explain the current stdio and HTTP config schema, auth/secret handling, validation, and session-versus-persistent lifecycle
- **AND** it SHALL direct the caller to the exact server's current authoritative MCP documentation for command, URL, arguments, auth, and capabilities
- **AND** it SHALL not claim that OneTool maintains a server-specific preset

#### Scenario: Server is configured but disconnected
- **GIVEN** a configured server is enabled but not connected
- **WHEN** its setup topic is requested
- **THEN** the report SHALL show configured/enabled/disconnected state and the sanitized last error
- **AND** it SHALL recommend one named-server recovery action without affecting unrelated servers

#### Scenario: Configured server values are redacted
- **GIVEN** a configured stdio or HTTP server contains environment, header, bearer, or OAuth configuration
- **WHEN** config/setup help is rendered
- **THEN** transport shape, key names, and OAuth scopes MAY be shown
- **AND** tokens, secret expansions, sensitive header values, and credential values SHALL be redacted

### Requirement: Trusted-execution safety help

Runtime help SHALL expose deterministic, version-correct guidance for OneTool's execution trust
boundary and active security controls.

#### Scenario: Security workflow help is requested
- **WHEN** security workflow help is requested
- **THEN** it SHALL state that executed Python has full builtins and the validator is not a sandbox
- **AND** it SHALL explain process/user/environment isolation, AST rules, path boundaries, secret handling, and external-content sanitization
- **AND** it SHALL direct the caller to `ot.security()` for current effective decisions
