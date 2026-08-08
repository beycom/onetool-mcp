## ADDED Requirements

### Requirement: MCP Proxy Configuration Validation

OneTool SHALL reject invalid MCP proxy transport, authentication, timeout, and namespace configurations during configuration loading.

#### Scenario: Valid HTTP server
- **WHEN** an HTTP server supplies a non-empty HTTP or HTTPS URL and optional headers
- **THEN** configuration loading SHALL succeed
- **AND** the server SHALL NOT supply stdio-only command, argument, environment, or inheritance fields

#### Scenario: Valid HTTP authentication
- **WHEN** an HTTP server uses bearer authentication
- **THEN** it SHALL supply a non-empty token and SHALL NOT supply scopes
- **WHEN** an HTTP server uses OAuth authentication
- **THEN** it SHALL NOT supply a token
- **AND** configured OAuth scope entries SHALL be non-empty after trimming and deduplicated in configured order

#### Scenario: Valid stdio server
- **WHEN** a stdio server supplies a non-empty command and a positive timeout
- **THEN** configuration loading SHALL succeed
- **AND** the server SHALL NOT supply URL, header, or authentication fields

#### Scenario: Invalid transport shape
- **WHEN** a server omits its required URL or command, supplies a non-positive timeout, uses a non-HTTP URL scheme, or explicitly supplies fields owned by the other transport
- **THEN** configuration loading SHALL fail before any connection attempt
- **AND** the validation error SHALL identify the server and conflicting field or rule

#### Scenario: Ambiguous proxy namespace
- **WHEN** server keys collide after replacing hyphens with underscores, or a key claims the reserved `proxy` namespace
- **THEN** configuration loading SHALL fail with the conflicting server names
- **AND** unrelated valid server names SHALL remain accepted

#### Scenario: Environment-backed bearer token
- **WHEN** a valid bearer token is configured as an environment placeholder
- **THEN** configuration loading SHALL preserve the placeholder for point-of-use expansion
- **AND** the expanded non-empty token SHALL be used when the HTTP client is created
