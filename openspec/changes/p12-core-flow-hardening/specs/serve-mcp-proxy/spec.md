## ADDED Requirements

### Requirement: Downstream Result Conversion

The system SHALL correctly convert every downstream MCP content-block type a proxied tool can return, and SHALL NOT force-coerce plain text results into a different type.

#### Scenario: EmbeddedResource content is surfaced, not dropped
- **GIVEN** a proxied MCP tool returns a result whose content includes a `types.EmbeddedResource` block (payload under `.resource`)
- **WHEN** the proxy call completes
- **THEN** the resource's text (or a binary marker, if the resource is not text) SHALL be surfaced in the returned result
- **AND** the caller SHALL NOT receive `"Tool returned empty response."`

#### Scenario: Structured-only result falls back to structured_content
- **GIVEN** a proxied MCP tool returns a result with no text/embedded content parts but with `structured_content` (or `.data`) populated
- **WHEN** the proxy call completes
- **THEN** the returned result SHALL be derived from `structured_content`/`.data`
- **AND** the caller SHALL NOT receive `"Tool returned empty response."`

#### Scenario: Plain string result is not force-coerced
- **GIVEN** a proxied MCP tool returns a single text result `"007"`
- **WHEN** the proxy call completes
- **THEN** the returned result SHALL be the string `"007"`
- **AND** it SHALL NOT be coerced to the integer `7`

#### Scenario: JSON-shaped text is still parsed
- **GIVEN** a proxied MCP tool returns a single text result that, stripped of whitespace, starts with `{` or `[` (e.g. `"[1,2]"` or `'{"a":1}'`)
- **WHEN** the proxy call completes
- **THEN** the text SHALL be parsed as JSON and returned as the corresponding structured Python value

#### Scenario: Non-JSON-shaped scalars pass through as text
- **GIVEN** a proxied MCP tool returns a single text result that does not start with `{` or `[` (e.g. `"null"`, `"true"`, `"NaN"`, `"42"`)
- **WHEN** the proxy call completes
- **THEN** the text SHALL be returned unchanged as a string
- **AND** it SHALL NOT be parsed into `None`, a boolean, a float, or an int

### Requirement: Thread-Safe Tool Listing

The system SHALL allow `list_tools()` to be read concurrently with proxy connection mutations without raising an unhandled concurrency error.

#### Scenario: Concurrent connect during a full tool listing
- **GIVEN** a worker thread is iterating `list_tools(server=None)` across all connected servers
- **AND** a background connection adds a new server's tools to the internal tool registry concurrently on the event-loop thread
- **THEN** `list_tools(server=None)` SHALL complete without raising `RuntimeError: dictionary changed size during iteration`
- **AND** it SHALL return either the pre- or post-connect view of the tool set (either is acceptable; a crash is not)
