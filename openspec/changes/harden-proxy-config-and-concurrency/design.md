## Context

Proxy configuration is represented by nested Pydantic models, but transport-specific fields are currently accepted in incompatible combinations. Proxy calls also use one per-server lock because the downstream elicitation callback exposes a downstream request ID, not a reliable identifier for the originating OneTool `run` request.

The downstream FastMCP session supports concurrent request/response correlation, but its elicitation callback cannot prove which concurrent tool call caused an incoming elicitation request. Concurrency therefore must distinguish calls that have no interactive owner from calls that may forward elicitation.

## Goals / Non-Goals

**Goals:**

- Reject invalid server/auth shapes and ambiguous namespace names while loading YAML.
- Preserve environment placeholders until the existing point-of-use expansion.
- Run bounded non-interactive calls concurrently on one downstream session.
- Give interactive calls exclusive server access so the singular elicitation callback always has exactly one possible owner.
- Keep capacity waits within the existing absolute call deadline and clean all gate state during lifecycle transitions.

**Non-Goals:**

- Add compatibility aliases or migration handling for invalid configurations.
- Add a callback-port or concurrency configuration field.
- Infer elicitation ownership from queue order, timing, or the downstream request ID.
- Create a downstream client/session pool in this change.

## Decisions

1. **Validate with Pydantic model validators.** `AuthConfig` validates fields that depend on auth type; `McpServerConfig` validates transport-specific fields using `model_fields_set` where explicitly supplied default-valued fields must still be rejected; `OneToolConfig` validates reserved and colliding server keys. This keeps failures on the normal configuration-validation path. Delayed manager-side validation was rejected because it produces network-shaped failures after startup.

2. **Normalize OAuth scopes at configuration load.** Scope strings are stripped, empty entries rejected, and duplicates removed while preserving order. Bearer tokens remain unexpanded strings until connection setup, preserving the established secret-expansion boundary.

3. **Use a bounded shared/exclusive per-server gate.** Calls without an originating interactive request use shared capacity and may overlap up to a fixed internal bound. Calls with an originating request acquire exclusive capacity and are the only calls registered for elicitation forwarding. A plain semaphore was rejected because it could allow a detached call's elicitation to borrow an interactive caller's context.

4. **Prefer waiting interactive calls.** Once an exclusive caller is waiting, new shared callers wait too. This avoids indefinite interactive starvation while allowing already-running non-interactive calls to finish.

5. **Keep interactive calls serial until correlation is proven.** FastMCP's downstream `RequestContext.request_id` identifies the incoming elicitation request, not the originating outgoing tool request. Session pooling could isolate interactive calls but would substantially expand OAuth, subprocess, schema-refresh, and exact-once lifecycle ownership; it is deferred.

## Risks / Trade-offs

- **Interactive-capable calls remain serial** → This preserves correct ownership; non-interactive/detached work still gains concurrency without cross-talk.
- **A fixed capacity may not suit every server** → Use a conservative internal bound and avoid adding an unrequested public config field.
- **Stricter validation breaks invalid existing files** → Fail with server/field-specific messages and no compatibility fallback, as required by project policy.
- **Cancellation inside gate transitions could leak counters** → Mutate counters only while holding the condition and release them in cancellation-safe context-manager cleanup.
