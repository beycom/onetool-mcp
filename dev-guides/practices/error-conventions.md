# Error conventions

Preserve native MCP error status and content types. Do not turn a tool error into a successful string/dictionary, parse arbitrary text as JSON, or hide an unavailable server as an empty successful call.

Local config failures use `ConfigError`; CLI argument/config failures exit 2, fatal runtime failures exit 1, and orderly exit is 0. Config diagnostics name locations/categories without printing rejected values. Missing variables are named without their values.

Use FastMCP `ToolError` at gateway/admin boundaries. Include a safe server/tool identifier and a next step where useful. Backend status retains redacted exception text, prefixed by name/type and capped at 300 characters. Logs get categories, not that text.

Cancellation is control flow. Propagate client cancellation and shutdown. Operations tracks the tasks its drain cancels; only those become explicit unknown-outcome errors after uncancel. Keep the task sets bounded by active work and clear membership on every path.

A timeout or transport loss after dispatch leaves the result unknown. Never retry automatically or recommend repeating to obtain lost output. Oversized output gives a private path and preview; a failed retention attempt explicitly says not to replay. Check [Python behavior](../../docs/python.md) before changing these messages.
