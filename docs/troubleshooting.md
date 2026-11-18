# Troubleshooting

Start with `onetool check-config --config PATH`. It reports validation locations/categories or missing environment-variable names without printing rejected values. Exit 2 means arguments/config, exit 1 means fatal runtime failure, and exit 0 means an orderly command or shutdown.

## Missing tools or unavailable servers

Call `onetool_status`. If a server's tools are missing from search, inspect its state and last sanitized error. Discovery skips unavailable servers; it does not list placeholder tools. Each search or execute still fetches every enabled server's catalog. A hung HTTP server can delay it by up to that server's `timeout_seconds`. Lower the timeout or set `enabled: false` for a flaky server.

States are disabled, lazy, ready and error. Status includes observed tool counts, versions, process/config paths, timeouts and referenced environment-variable presence. It never opens an upstream connection. Some client SDKs send a separate tools/list request after reading a result; that discovery can connect.

The last error has the server name, exception type and redacted text, capped at about 300 characters. Check executable paths and working directories. Preserve virtualenv executable symlinks: their directory identifies the environment.

Raw upstream stderr is discarded because it can contain arguments, results or secrets. To see a server's startup stderr, run its configured command directly with the same cwd and environment. Review that output before sharing it. The gateway's own optional rotating log contains event categories and timings.

## Authentication

Check referenced variable names and whether they are set. A header and OAuth cannot be used together for one server. OAuth requires a supported secure system keyring; a mixed secure/plaintext chain is rejected. Keyring storage failure does not fall back to a file.

For credentials, prefer `${NAME}` references. Every substituted value is masked in errors. Literal env/header values shorter than eight characters and literal argument values are not used as masks, to keep ordinary error text readable. Payloads are never intentionally logged. Paths in status/logs are local diagnostics and can identify your account.

## Reload and restart

`onetool_reload()` rereads and validates the complete YAML file before changing anything. Invalid config leaves running servers untouched. Changed execution/logging settings require a gateway process restart.

A valid reload stops new executions, waits up to five seconds for active work, cancels the rest and closes all upstreams. It resets their state and reconnects lazily. Interrupted dispatched calls have unknown outcomes and must not be replayed.

`onetool_restart_server(name)` resets only that loaded server. It uses the same admission/drain rule. To disable a server, edit `enabled: false` and reload. To restart the gateway process itself, reconnect it from your MCP client.

Client cancellation and shutdown propagate cancellation without generating a new tool response. Cancelling a reload/restart while it waits for active work reopens admission. Drain cancellation produces an explicit unknown-outcome error for the affected caller.

A single ingress connection stayed open for 60 restart/reload pairs. RSS after pairs 20/40/60 was 102400/102544/102640 KiB, with 11 file descriptors throughout and all retired backend processes gone. Growth flattened. A separate weakref/GC control found no accumulation of live backend/client objects after collection; these controls do not prove a continuing object leak. Restart the gateway to release retained process memory.

## Large responses and memory

Read the returned file path with your own tools. Check its byte count and SHA-256 if moving it elsewhere. Do not rerun the execution to recover output. Files are removed on orderly shutdown and can be evicted under the directory cap.

The inline cap and 16 MiB retention limit apply after upstream reception. They cannot prevent protocol parsing and sandbox projection from allocating memory. A 20 MiB fixture response raised gateway peak RSS to about 1.39 GB on macOS arm64. Three consecutive calls retained 1,337,296, 1,337,536 and 1,337,536 KiB after collection and idle, so no linear growth was observed in that control. A large call can leave the process using roughly 1.3 GiB.

Keep large upstream responses smaller when possible, or connect that server directly. Restart the gateway to release retained memory. HTTP's upstream SSE-event cap does not bound application/json responses. This is an upstream limitation; OneTool does not add another receive pipeline.

A result over 16 MiB or a failed disk write returns an explicit no-replay message. A crash may leave private temp files for the operating system to clean up.
