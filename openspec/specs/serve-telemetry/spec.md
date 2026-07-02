# serve-telemetry Specification

## Purpose

Anonymous usage telemetry fired at server start via PostHog.
Covers event types (server-installed, server-upgraded, server-started),
machine UUID generation and persistence, opt-out mechanism, and disclosure.

## Requirements

### Requirement: Anonymous startup ping

On each server start, the server SHALL fire a single anonymous POST event to
PostHog with event type, version, OS, architecture, Python version, and machine
UUID. The request SHALL be non-blocking and SHALL NOT affect server startup time
or reliability. All failures SHALL be silently ignored.

#### Scenario: Ping fires on start
- **WHEN** the MCP server starts
- **THEN** a POST is sent to the PostHog capture endpoint with properties
  `version`, `os`, `arch`, `python_version`, and `$process_person_profile: false`

#### Scenario: Ping does not block startup
- **WHEN** the PostHog endpoint is unreachable
- **THEN** the server starts normally with no error or delay

### Requirement: Install event on first run

The server SHALL fire a `server-installed` event on the first ever start
(marker file absent). After firing, the marker file SHALL be written with the
current version and a newly generated anonymous UUID.

#### Scenario: First start fires server-installed
- **WHEN** the marker file does not exist and the server starts
- **THEN** event `server-installed` is sent
- **AND** the marker file is created with the current version on line 1 and a new UUID4 on line 2

#### Scenario: Subsequent start fires server-started
- **WHEN** the marker file exists with the current version and the server starts
- **THEN** event `server-started` is sent

### Requirement: Upgrade event on version change

The server SHALL fire a `server-upgraded` event when the running version differs
from the version stored in the marker file. The marker SHALL be updated with the
new version after firing.

#### Scenario: Version change fires server-upgraded
- **WHEN** the marker file contains a version string different from the running version
- **THEN** event `server-upgraded` is sent with `version_from` and `version_to` properties
- **AND** the marker file is updated with the new version (UUID is preserved)

### Requirement: Machine UUID generation and persistence

The server SHALL generate a random UUID4 on first run and persist it in the
marker file. The same UUID SHALL be reused on all subsequent starts.

#### Scenario: UUID generated on install
- **WHEN** the marker file does not exist and the server starts
- **THEN** a UUID4 is generated and written to line 2 of the marker file
- **AND** the UUID is sent as the PostHog `distinct_id`

#### Scenario: UUID reused on subsequent starts
- **WHEN** the marker file exists with a UUID on line 2
- **THEN** the existing UUID is read and sent as `distinct_id`
- **AND** no new UUID is generated

#### Scenario: Old-format marker migration
- **WHEN** the marker file exists with only one line (version string, no UUID)
- **THEN** a new UUID4 is generated
- **AND** the marker file is updated to the two-line format with the UUID on line 2
- **AND** the event type is determined normally based on the version comparison

### Requirement: Marker file location

The marker file SHALL be stored as `telemetry` in the OT_DIR (alongside
`onetool.yaml`). Most users have a single global config, so the UUID is
effectively machine-scoped for them.

#### Scenario: Marker file path
- **GIVEN** the config file is at `{OT_DIR}/onetool.yaml`
- **WHEN** the server starts
- **THEN** the marker file is read from and written to `{OT_DIR}/telemetry`

### Requirement: Opt-out via environment variable

The server SHALL respect the `DO_NOT_TRACK` environment variable. When set to
a non-empty, non-zero value, no telemetry event SHALL be sent.

#### Scenario: DO_NOT_TRACK disables telemetry
- **WHEN** `DO_NOT_TRACK=1` is set and the server starts
- **THEN** no event is sent to PostHog

#### Scenario: DO_NOT_TRACK=0 does not disable telemetry
- **WHEN** `DO_NOT_TRACK=0` is set and the server starts
- **THEN** telemetry fires normally

### Requirement: Opt-out via config flag

The server SHALL respect `telemetry.enabled: false` in `onetool.yaml`.
When set to `false`, no telemetry event SHALL be sent.

#### Scenario: Config flag disables telemetry
- **WHEN** `telemetry.enabled: false` is set in `onetool.yaml` and the server starts
- **THEN** no event is sent to PostHog

### Requirement: Telemetry disclosure

The project SHALL provide a `docs/telemetry.md` page that clearly states what
data is collected, what is not collected, and how to opt out.

#### Scenario: Disclosure page exists
- **WHEN** a user reads `docs/telemetry.md`
- **THEN** they can find: collected fields (including machine UUID and IP), fields not
  collected, opt-out instructions, and an explanation of the marker file
