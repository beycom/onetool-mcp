# Troubleshooting

Start with `onetool check-config --config PATH`. It reports validation locations/categories or missing environment-variable names without printing rejected values. Exit 2 means arguments/config, exit 1 means fatal runtime failure, and exit 0 means an orderly command or shutdown.

## Missing tools or unavailable servers

Call `onetool_status`. If a server's tools are missing from search, inspect its state and last sanitized error. Discovery skips unavailable servers; it does not list placeholder tools. Each search and each execution that dispatches tools fetches every enabled server's catalog. A hung HTTP server can delay it by up to that server's `timeout_seconds`. Lower the timeout or set `enabled: false` for a flaky server.

States are disabled, lazy, ready and error. Status includes observed tool counts, versions, process/config paths, timeouts and referenced environment-variable presence. It never opens an upstream connection. Some client SDKs send a separate tools/list request after reading a result; that discovery can connect.

The last error has the server name, exception type and redacted text, capped at about 300 characters. Check executable paths and working directories. Preserve virtualenv executable symlinks: their directory identifies the environment.

Raw upstream stderr is discarded because it can contain arguments, results or secrets. To see a server's startup stderr, run its configured command directly with the same cwd and environment. Review that output before sharing it. The gateway's own optional rotating log contains event categories and timings.

## Authentication

Check referenced variable names and whether they are set. A header and OAuth cannot be used together for one server. OAuth requires a supported secure system keyring; a mixed secure/plaintext chain is rejected. Keyring storage failure does not fall back to a file.

For credentials, prefer `${NAME}` references. Every substituted value is masked in errors. Literal env/header values shorter than eight characters and literal argument values are not used as masks, to keep ordinary error text readable. Payloads are never intentionally logged. Paths in status/logs are local diagnostics and can identify your account.

## Server controls and reload

`onetool_servers(action, name=None)` replaces the old restart tool. Actions are `list`, `status`, `enable`, `disable` and `restart`. List/status are read-only and open no connection. They show configured/session enabled, state, transport, tool count and sanitized errors, without arguments or credential values. Unknown names list configured names.

Enable connects immediately and reports a tool count; an already-ready server is unchanged. Disable removes that server from discovery, waits up to five seconds for its calls, cancels the rest and closes its process. Calls to other servers continue. Toggles never edit YAML and reset on successful reload or gateway process restart. Interrupted outcomes are unknown and must not be replayed.

Restart validates the whole disk config first, refreshes only the named definition and reconnects it enabled for the session. Other connections/overrides stay intact; the response lists definitions needing reload and execution/logging changes needing a gateway restart. Invalid disk config changes nothing. Controls are serialized against reload.

`onetool_reload()` validates the complete candidate before draining all work and replacing all backends. Invalid config leaves connections and overrides untouched. Changed execution/logging settings require a gateway process restart. A successful reload clears overrides and reconnects lazily.

Client cancellation and shutdown propagate without a new tool response. Cancelling an admin drain reopens execution admission; only drain-initiated cancellations become unknown-outcome errors. Reconnect the gateway from the MCP client to restart the process.

A single ingress connection stayed open for 60 restart/reload pairs. RSS after pairs 20/40/60 was 102400/102544/102640 KiB, with 11 file descriptors throughout and all retired backend processes gone. Growth flattened. A weakref/GC control found no live client accumulation; it does not prove a continuing object leak.

## Large responses and memory

Read the returned file path with your own tools. Check its byte count and SHA-256 if moving it elsewhere. Do not rerun the execution to recover output. Files are removed on orderly shutdown and can be evicted under the directory cap.

The inline cap and 16 MiB retention limit apply after upstream reception. They cannot prevent the MCP SDK's stdio line reader from repeatedly copying a large JSON-RPC line. That quadratic reassembly, rather than Monty or JSON parsing, caused the measured peak. A 20 MiB fixture response raised gateway peak RSS to about 1.39 GB on macOS arm64. Three consecutive calls retained 1,337,296, 1,337,536 and 1,337,536 KiB after collection and idle, so no linear growth was observed in that control. A large call can leave the process using roughly 1.3 GiB.

Prefer HTTP transport for servers returning large values: the isolated 20 MiB control used about 129 MiB over HTTP versus about 1.2 GB over stdio. Keep upstream responses smaller when possible. Restart the gateway to release retained memory. HTTP's upstream SSE-event cap does not bound application/json responses. This is an upstream limitation; OneTool does not add another receive pipeline.

A result over 16 MiB or a failed disk write returns an explicit no-replay message. A crash may leave private temp files for the operating system to clean up.
