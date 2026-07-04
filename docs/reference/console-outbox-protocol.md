# Console Outbox Protocol

OneTool MCP exposes a narrow signed outbox for the separate OneTool Console App when `direct.host.enabled: true`.

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
| `display.message.created` | Display message metadata, payload mode, bounded preview, and stable 12-character lowercase hex message ID |

Consumers may ignore unknown future event types.

## Payload Modes

| Mode | Meaning |
|------|---------|
| `inline` | Bounded JSON-compatible content included in the event |
| `file_ref` | Canonical absolute local file path plus MIME and size metadata |
| `file_diff_ref` | Canonical diff path or structured old/new paths plus MIME and size metadata |

Console owns local file preview/blob APIs and must validate all paths against published `allowed_roots`.

## Retention

Polling is at-least-once. A poll response does not remove events. MCP removes events only when they are acknowledged or when bounded FIFO retention is exceeded.

Protocol schemas and fixtures are checked in under:

- `tests/fixtures/console-protocol/schemas/`
- `tests/fixtures/console-protocol/fixtures/`

