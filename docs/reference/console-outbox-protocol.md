# Console Outbox Protocol

OneTool MCP exposes a narrow signed outbox for the separate OneTool Console App when `direct.host.enabled: true`.

**Status: protocol v1 — served from 3.0.0, inline payloads only; file modes ship with the full display experience in 3.1.** The endpoints and MCP-owned outbox state ship in 3.0.0 emitting `inline` payloads only. The `file_ref` and `file_diff_ref` payload modes remain part of protocol v1 but are not emitted until 3.1.

## Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/console/outbox` | `GET` | Poll retained Console events without mutating queue state |
| `/api/console/outbox/ack` | `POST` | Acknowledge consumed events so MCP can drop them early |

Console requests use `auth/console-outbox.key`. This key is separate from `auth/mcp-direct.key` and does not authorize `/run`.

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

## Acknowledgement

Acknowledgement (`POST /api/console/outbox/ack`) is keyed on protocol identity, MCP instance identity, and `acked_through` only. It does **not** require a `batch_id`; a `batch_id` field, if present, is ignored. The `batch_id` returned in a poll batch remains available for logging and diagnostics but is not part of the ack contract.

## Retention

Polling is at-least-once. A poll response does not remove events. MCP removes events only when they are acknowledged or when bounded FIFO retention is exceeded.

Each poll batch includes an `oldest_retained` integer: the sequence of the oldest retained entry, or `acked_through` when no entries are retained (for example an empty outbox at startup reports `oldest_retained: 0`). A consumer whose cursor is `c` detects retention-driven loss when `oldest_retained > c + 1` — events `c+1 .. oldest_retained-1` were evicted by bounded retention before they were acknowledged.

## Tolerant readers

Consumers MUST ignore unknown fields anywhere in the protocol — outbox batches, event envelopes, and payloads. Within `protocol_version: 1`, servers MAY add new fields without a version bump. The checked-in JSON Schemas keep `additionalProperties: false` as a strict producer-conformance check for the shipped server; they are not a consumer validation contract.

Protocol schemas and fixtures are checked in under:

- `tests/fixtures/console-protocol/schemas/`
- `tests/fixtures/console-protocol/fixtures/`

