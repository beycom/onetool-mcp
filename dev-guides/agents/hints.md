# Agent hints

- Read `AGENTS.md`, the active record and its evidence before implementing. Preserve the user's scope and pre-existing changes.
- Check the pinned FastMCP public APIs before adding code. Prove new upstream assumptions with a small POC. Use documented Provider hooks; do not access private attributes.
- Keep one runtime object and one event loop. Python execution is native CodeMode, with fresh variables per request.
- Treat cancellation sources separately. Client cancellation/shutdown propagate; only the operation's own drain cancellation becomes a tool error.
- Never replay a dispatched call. Unknown outcomes remain unknown, including timeouts and connection loss.
- Keep payloads out of diagnostics. Use server/tool identifiers, duration, outcomes and safe categories. Review configured-secret handling when changing error text.
- Test gateway contracts through the real fixture protocol. Do not duplicate upstream suites or introduce credentials into routine tests.
- Run focused checks while building, one `just check` at the final batch boundary. Reuse valid evidence; explain failures and skipped coverage.
- Read [testing](../practices/testing.md) before broad checks and [workspace](../practices/workspace.md) before Git operations. Never modify preserved checkouts.
- Do not put session roles, temporary decisions or unmeasured performance claims in durable guides. Keep task history in its planning record.
