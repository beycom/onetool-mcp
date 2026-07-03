## MODIFIED Requirements

### Requirement: Tool Detail

The `ot.tool_info()` function SHALL return detailed info (signature + args) for one or more tools.

On an exact-name lookup that finds no match, it SHALL return an error dict carrying a
`did_you_mean` suggestion list instead of an empty dict, so the contract's designated
inspect-before-you-call move never dead-ends silently.

#### Scenario: Exact name lookup
- **GIVEN** `name="brave.search"` parameter
- **WHEN** `ot.tool_info(name="brave.search")` is called
- **THEN** it SHALL return a single dict

#### Scenario: Pattern lookup
- **GIVEN** `pattern="brave"` parameter
- **WHEN** `ot.tool_info(pattern="brave")` is called
- **THEN** it SHALL return a list of dicts for all matching tools

#### Scenario: Short alias resolves in pattern and name
- **GIVEN** a pack metadata short alias (e.g. `"ctx"` for `"ot_context"`)
- **WHEN** `ot.tool_info(pattern="ctx")` or `ot.tool_info(name="ctx.ask")` is called
- **THEN** it SHALL resolve the alias and match against the full pack name

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter
- **WHEN** `ot.tool_info(name="brave.search", info="min")` is called
- **THEN** each entry SHALL include: `{name, signature, args}`
- **NOTE** This differs from `ot.tools(info="min")` which returns name strings only. `tool_info` always returns dicts (detail mode), while `tools` returns compact list entries.

#### Scenario: Info level default
- **GIVEN** `info="default"` parameter (or no info parameter)
- **WHEN** `ot.tool_info(name="brave.search")` is called
- **THEN** each entry SHALL include: `{name, signature, args, description, source}`
- **AND** description SHALL be truncated to 200 characters

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.tool_info(pattern="brave.search", info="full")` is called
- **THEN** each entry SHALL include: `{name, signature, description, source}`
- **AND** each entry SHALL include `{args, returns, example}` when available

#### Scenario: Proxy tool signature from schema
- **GIVEN** a proxy MCP server with tools exposing `inputSchema`
- **WHEN** `ot.tool_info(pattern="github.search", info="full")` is called
- **THEN** signature SHALL be derived from schema properties (e.g., `github.search(query: str, repo: str = '...')`)
- **AND** required parameters SHALL appear without defaults
- **AND** optional parameters SHALL show default values or `'...'` placeholder

#### Scenario: Exact name miss returns error and suggestions
- **GIVEN** no tool named `"brave.serch"` exists (a typo of `"brave.search"`)
- **WHEN** `ot.tool_info(name="brave.serch")` is called
- **THEN** it SHALL return a dict with exactly the keys `error` and `did_you_mean` (not an empty dict `{}`)
- **AND** `error` SHALL be a non-empty string stating that no tool with that name was found
- **AND** `did_you_mean` SHALL be a list (possibly empty) of full tool names (`"pack.tool"`) that are similar to the requested name, computed by fuzzy string similarity against the complete unfiltered set of local and proxied tool names (not the pattern-filtered result set, which is empty at this point by construction)
- **AND** for the `"brave.serch"` example specifically, `did_you_mean` SHALL be non-empty and SHALL include `"brave.search"`

#### Scenario: Exact name miss with no plausible match
- **GIVEN** `name="zzzzz.nonexistent"` matches no tool and no tool name is meaningfully similar
- **WHEN** `ot.tool_info(name="zzzzz.nonexistent")` is called
- **THEN** it SHALL still return `{"error": ..., "did_you_mean": []}` — an empty `did_you_mean` list, never a missing key or a bare `{}`
