## Why

Invalid proxy transport/authentication combinations currently survive configuration loading and fail later with misleading runtime errors. At the same time, one shared per-server call lock prevents independent downstream work from overlapping even when request ownership can remain isolated.

## What Changes

- **BREAKING** Reject invalid MCP server transport, authentication, timeout, and namespace configurations during configuration loading.
- **BREAKING** Reject server names that collide after Python-safe normalization or claim the reserved `proxy` namespace.
- Permit bounded concurrent proxy calls only when each call's elicitation remains bound to its exact originating root request.
- Include concurrency-capacity waits in the existing absolute operation deadline and preserve serial execution when safe ownership cannot be established.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `serve-configuration`: Define valid MCP server transport/authentication combinations, positive timeouts, and unambiguous server namespace names.
- `serve-mcp-proxy`: Define bounded concurrent downstream calls with exact elicitation ownership, deadline accounting, and lifecycle cleanup.

## Impact

- Configuration models and YAML loading tests become stricter; previously accepted invalid server entries will fail at load time.
- Proxy manager call scheduling and elicitation ownership change while retaining existing public call syntax and timeout behavior.
- Execution namespace construction can assume validated, collision-free server aliases.
