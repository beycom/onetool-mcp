# Console Outbox Protocol

OneTool MCP exposes a narrow signed outbox for the separate OneTool Console App when `direct.host.enabled: true`.

**Status: protocol v1.** The endpoint and MCP-owned outbox emit `inline`,
`file_ref`, and `file_diff_ref` payload modes. File-reference events carry paths
only; the Console reads file content locally after validating `allowed_roots`.

## Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/console/outbox` | `GET` | Poll retained Console events without mutating queue state |

Console requests use `auth/console-outbox.key`. This key is separate from `auth/mcp-direct.key` and does not authorize `/run`. The key file is ensured **eagerly** when the direct API app is created (as soon as the Console outbox route is mounted at startup), not lazily on the first request, so a Console started right after MCP is up can authenticate immediately.

## Discovery

The direct API auto-increments past `direct.host.port` when the preferred port is taken, so a fixed configured port cannot be relied on to find a running instance. To let consumers discover the actual bound port — and enumerate multiple concurrently running MCP instances — MCP writes a discovery file per instance under `<ot-dir>/runtime/direct-api/`.

| Property | Value |
|----------|-------|
| Path | `<ot-dir>/runtime/direct-api/<instance_id>.json` |
| Written | When the direct API successfully binds (the final auto-incremented port is known) |
| Removed | On clean MCP shutdown |
| Mode | `0600` |
| Write method | Atomic: temp file in the same directory, then `os.replace` |

Body shape:

```json
{
  "instance_id": "mcp-<uuid4hex>",
  "port": 8766,
  "pid": 12345,
  "started_at": "2026-07-05T00:00:00+00:00"
}
```

- `instance_id` — the process's stable runtime instance identity (matches the id used elsewhere, e.g. Console outbox `instance_id`)
- `port` — the actual port the direct API bound, after auto-increment
- `pid` — the MCP process id
- `started_at` — ISO-8601 UTC timestamp of when the direct API bound

One file exists per live instance, so multiple concurrently running MCP processes each get their own discovery file in the same directory.

**Staleness rule for consumers:** a discovery file is stale if its recorded `pid` is not a live process. Consumers MUST check process liveness (for example `os.kill(pid, 0)` semantics — no exception or a `PermissionError` means alive; `ProcessLookupError` means dead) before trusting a file's `port`, and MUST ignore stale files rather than connecting to them. MCP does not read a discovery file back to double check it is unmodified before removing it on shutdown, and consumers must never assume the file's absence means anything other than "no live discovery record from this MCP" — it is not itself an auth or readiness signal.

MCP also opportunistically sweeps stale sibling files (dead `pid`) from `<ot-dir>/runtime/direct-api/` at its own direct API startup, but consumers SHALL NOT depend on that sweep for correctness — always apply the staleness rule when reading the directory directly.

No discovery file is written when `direct.host.enabled: false` (no direct API listener is started in that case either).

## Protocol Identity

All protocol payloads include:

```json
{
  "protocol": "onetool.console",
  "protocol_version": 1
}
```

Events use stable envelopes with string IDs, monotonic integer `sequence`, ISO-8601 timestamps, and JSON-compatible payloads.

## Event Types

| Type | Payload |
|------|---------|
| `instance.snapshot` | Instance identity, cwd, repo root, config paths, allowed roots, status, message count, update timestamp, and runtime metadata |
| `console.message.created` | Display message metadata, payload mode, bounded preview, and stable 12-character lowercase hex message ID |

Consumers may ignore unknown future event types.

The server emits `instance.snapshot` at startup, on instance change, and when snapshot-relevant state (status or message count) changes — not on every poll or status call.

## Payload Modes

| Mode | Meaning |
|------|---------|
| `inline` | Bounded JSON-compatible content included in the event |
| `file_ref` | Canonical absolute local file path plus MIME and size metadata |
| `file_diff_ref` | Canonical diff path or structured old/new paths plus MIME and size metadata |

Console owns local file preview/blob APIs and must validate all paths against published `allowed_roots`.

## Cursor polling

Consumers own their progress cursor. Each poll supplies `after=<cursor>` and advances to the returned `next_cursor`; omitting `after` starts at cursor `0`. The `batch_id` is available for logging and diagnostics only. Polling never removes events, so multiple Console processes can consume the same MCP instance independently.

## Retention

Polling is at-least-once for each cursor. A poll response does not remove events. The producer removes entries when bounded FIFO retention is exceeded or when their underlying Console messages are explicitly removed or cleared.

Each poll batch includes an `oldest_retained` integer: the sequence of the oldest retained entry, or one greater than the latest evicted sequence when no entries are retained (an empty outbox at startup reports `oldest_retained: 1`). A consumer whose cursor is `c` detects loss when `oldest_retained > c + 1` — events `c+1 .. oldest_retained-1` are no longer retained.

The producer keeps message metadata and IDs in memory, but not preview or inline
payload bodies. Those fields are written through to the runtime instance's
session-scoped message files and hydrated when a poll response is serialized.
If a message body disappears while a poll is hydrating it, the producer emits a
schema-valid body-free payload with `preview: null` and, for inline messages,
`content: null`.

## Tolerant readers

Consumers MUST ignore unknown fields anywhere in the protocol — outbox batches, event envelopes, and payloads. Within `protocol_version: 1`, servers MAY add new fields without a version bump. The checked-in JSON Schemas keep `additionalProperties: false` as a strict producer-conformance check for the shipped server; they are not a consumer validation contract.

Protocol schemas and fixtures are checked in under:

- `tests/fixtures/console-protocol/schemas/`
- `tests/fixtures/console-protocol/fixtures/`
