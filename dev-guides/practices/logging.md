# Logging

Use `onetool.diagnostics.event` and the runtime's logger. Standard-library handlers send JSON events to stderr and optionally a rotating file. `logging_context` installs/restores the owned handlers once. Do not add per-call handlers or enable wire/debug logs from upstream libraries.

Every event has a timestamp, severity, event name, request ID, server/tool identifiers, duration, outcome and error category. INFO covers lifecycle/admin work, DEBUG records timings, WARNING/ERROR report failures. Emit fixed event names and safe categories, never raw exceptions or payloads.

Never log code, arguments, results, header values or environment values. Redaction is a second defense, not permission to pass payloads to a logger. Substituted values are masks at every length; literal env/header values become masks at eight characters. Keep the documented short-value limit visible.

Records are capped at 8 KiB, including escaped Unicode. Optional files rotate at 10 MiB with three backups; an opening failure is fatal startup. Raw child stderr is discarded. [Troubleshooting](../../docs/troubleshooting.md) explains running a failing upstream command directly for its stderr.

Use the current request ID across nested calls. Distinguish timeout from confirmed cancellation and report interrupted dispatched outcomes as unknown. Client-facing MCP logging remains the upstream protocol's separate channel.
