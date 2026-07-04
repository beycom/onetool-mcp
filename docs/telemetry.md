# Telemetry

OneTool fires a single anonymous event via the [PostHog](https://posthog.com) SDK on each server start. This gives the project basic usage visibility — how many machines are running OneTool, on which platforms, and which versions — without tracking individual users or their work.

## What is collected

| Field | Value |
|-------|-------|
| `event` | Event type: `server-installed`, `server-upgraded`, or `server-started` |
| `version` | OneTool version (e.g. `1.2.3`) |
| `os` | Operating system (e.g. `macOS`, `Linux`, `Windows`) |
| `arch` | CPU architecture (e.g. `arm64`, `x86_64`) |
| `python_version` | Python major.minor version (e.g. `3.12`) |
| `version_from` | Previous version — only on `server-upgraded` events |
| `version_to` | New version — only on `server-upgraded` events |
| machine UUID | Anonymous stable identifier stored as `telemetry` in your OT_DIR (alongside `onetool.yaml`) |
| IP address | Source IP of the machine running OneTool, captured by PostHog at ingestion |

## What is NOT collected

- User identity, account names, or any personal data
- Tool call contents, prompts, or AI responses
- File paths, config values, or secrets
- Person profiles (`$process_person_profile: false` is set on all events)

## How opt-out works

**Via config file** (`onetool.yaml`):

```yaml
telemetry:
  enabled: false
```

**Via environment variable:**

```bash
export DO_NOT_TRACK=1
```

When this env var is set to a non-empty, non-zero value, no event is sent.

## Marker file

OneTool writes a `telemetry` file in your OT_DIR (alongside `onetool.yaml`) containing the current version and an anonymous UUID to distinguish `server-installed`, `server-upgraded`, and `server-started` events. This file is local to your machine. Most users have a single config for their whole machine, so the UUID is effectively machine-scoped. The UUID is a randomly generated identifier with no link to your identity.
