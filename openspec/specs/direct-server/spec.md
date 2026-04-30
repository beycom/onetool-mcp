# direct-server Specification

## Purpose

Defines the `onetool direct start/stop/status/restart/logs` commands for managing the HTTP execution host. The server exposes a `/run` endpoint for stateful in-process command execution, enabling state persistence across `onetool direct run` invocations.

---

## Requirements

### Requirement: direct start

The system SHALL provide `onetool direct start` to launch an HTTP execution host as a daemon process.

Flags:
- `--config`/`-c` — path to `onetool.yaml`; optional (warning printed if omitted)
- `--secrets`/`-s` — path to secrets file; optional
- `--port`/`-p` — HTTP port (default: from `onetool.yaml` `direct.host.port`, fallback `8765`)

The host exposes a single endpoint: `POST /run` accepting `{"command": "..."}` and returning `{"result": "...", "success": true|false}`.

#### Scenario: Start execution host

- **WHEN** `onetool direct start --config onetool.yaml` is run
- **THEN** the HTTP host SHALL start as a daemon process
- **AND** the PID file SHALL be written to `~/.onetool/direct-server-{port}.pid` as JSON (includes pid, port, config, secrets, started, log)
- **AND** the log file SHALL be written to `~/.onetool/direct-server-{port}.log`
- **AND** a message SHALL be printed: `"Execution host started (PID <pid>) on port <port>"` followed by `"Log: <path>"`

#### Scenario: Start waits until host is ready

- **WHEN** `onetool direct start` completes
- **THEN** the command SHALL poll the TCP port until it accepts connections (up to 5 seconds)
- **AND** exit 0 if ready within 5 seconds, exit 1 otherwise

#### Scenario: No --config prints warning

- **WHEN** `onetool direct start` is run without `--config`
- **THEN** a warning SHALL be printed: `"Warning: no --config provided; starting with no tools loaded"`
- **AND** the host SHALL still start (zero tools loaded)

#### Scenario: Port already in use

- **WHEN** `onetool direct start` is run and the configured port is already bound
- **THEN** the command SHALL exit with code 1 and print: `"Port <port> is already in use"`

#### Scenario: Execute command via HTTP

- **WHEN** a POST to `/run` with body `{"command": "ot.debug()"}` is received
- **THEN** the host SHALL execute the command via `execute_command()`
- **AND** return `{"result": "<output>", "success": true}` with HTTP 200
- **AND** on execution error: return `{"result": "<error>", "success": false}` with HTTP 200 (not 500)

### Requirement: direct stop

The system SHALL provide `onetool direct stop` to gracefully stop a execution host.

Flags:
- `--port`/`-p` — port of the host to stop (default: 8765)

#### Scenario: Stop running server

- **WHEN** `onetool direct stop` is run and a host is running (valid PID file exists)
- **THEN** the server process SHALL be terminated gracefully
- **AND** the PID file SHALL be removed
- **AND** a message SHALL be printed: `"Execution host stopped"`

#### Scenario: No server running

- **WHEN** `onetool direct stop` is run and no PID file exists
- **THEN** the command SHALL print: `"No execution host running"` and exit with code 0

#### Scenario: Stale PID file

- **WHEN** `onetool direct stop` is run and the PID file exists but the process is dead
- **THEN** the stale PID file SHALL be removed
- **AND** the command SHALL print: `"Stale PID file removed (process was not running)"` and exit with code 0

### Requirement: direct status

The system SHALL provide `onetool direct status` to report the state of the execution host.

Flags:
- `--port`/`-p` — port of the host to query (default: 8765)

#### Scenario: Server running

- **WHEN** `onetool direct status` is run and the host is running
- **THEN** it SHALL print the PID, port, uptime, and log file path
- **AND** when available in PID metadata, it SHALL print host `config` and `secrets` paths
- **AND** exit with code 0

#### Scenario: Server not running

- **WHEN** `onetool direct status` is run and no host is running
- **THEN** it SHALL print: `"No execution host running"`
- **AND** exit with code 1

### Requirement: direct restart

The system SHALL provide `onetool direct restart` to stop and restart the execution host in one command.

Flags:
- `--config`/`-c` — override config path (defaults to saved value from PID file)
- `--secrets`/`-s` — override secrets path (defaults to saved value)
- `--port`/`-p` — target port (default: 8765)

#### Scenario: Restart running server

- **WHEN** `onetool direct restart` is run and a host is running
- **THEN** the running host SHALL be stopped
- **AND** a new host SHALL be started with the saved config and port
- **AND** explicit flags override the saved values

#### Scenario: Restart when no server running

- **WHEN** `onetool direct restart` is run and no host is running
- **THEN** a message SHALL be printed: `"No execution host running; starting fresh"` and start a new server
- **AND** a new host SHALL start using provided flags (or defaults)

### Requirement: direct logs

The system SHALL provide `onetool direct logs` to print recent server log output.

Flags:
- `--port`/`-p` — port of the host (default: 8765)
- `--lines`/`-n` — number of lines to show (default: 50)

#### Scenario: Print logs

- **WHEN** `onetool direct logs` is run
- **THEN** the last N lines of `~/.onetool/direct-server-{port}.log` SHALL be printed to stdout

#### Scenario: No log file

- **WHEN** `onetool direct logs` is run and no log file exists
- **THEN** the command SHALL print an error and exit with code 1

### Requirement: direct port and host configuration

The execution host port and routing mode SHALL be configurable in `onetool.yaml` under the `direct:` section.

Config fields:
- `direct.host.enabled` — host optimization switch (`false` = always in-process; `true` = auto-start when needed)
- `direct.host.port` — preferred host port (default: `8765`)
- `direct.host.timeout` — HTTP request timeout in seconds when routing to host (default: `120`)

#### Scenario: Port from config

- **GIVEN** `onetool.yaml` contains `direct.host.port: 9000`
- **WHEN** `onetool direct start -c onetool.yaml` is run without `--port`
- **THEN** the server SHALL listen on port 9000

#### Scenario: --port overrides config

- **GIVEN** `onetool.yaml` contains `direct.host.port: 9000`
- **WHEN** `onetool direct start -c onetool.yaml --port 8765` is run
- **THEN** the server SHALL listen on port 8765

#### Scenario: Default port when not in config

- **GIVEN** `onetool.yaml` does not contain a `direct.host.port` key
- **WHEN** `onetool direct start -c onetool.yaml` is run
- **THEN** the server SHALL listen on port 8765

#### Scenario: direct.host.enabled true — auto-start on first use

- **GIVEN** `onetool.yaml` contains `direct.host.enabled: true`
- **WHEN** `onetool direct run -c onetool.yaml "ot.debug()"` is run and no host is running
- **THEN** the host SHALL be auto-started as a background process before routing
- **NOTE** explicit `onetool direct start` is optional but supported for pre-warming

#### Scenario: direct.host.enabled false — no auto-start

- **GIVEN** `onetool.yaml` contains `direct.host.enabled: false`
- **WHEN** `onetool direct run "ot.debug()"` is run and no host is running
- **THEN** the command SHALL execute in-process

#### Scenario: Auto allocation from preferred port to 65535

- **GIVEN** `onetool.yaml` contains `direct.host.enabled: true` and `direct.host.port: 9000`
- **WHEN** the MCP server starts
- **THEN** it SHALL try ports in order `9000, 9001, ... , 65535` until one binds successfully
- **AND** it SHALL fail startup with a clear error if all candidate ports are unavailable

#### Scenario: Enabled startup failure aborts MCP startup

- **GIVEN** `direct.host.enabled: true`
- **AND** auto-host startup fails
- **WHEN** MCP server startup runs
- **THEN** MCP startup SHALL fail with a clear error

### Requirement: per-port PID and log files

The system SHALL use per-port PID and log files to support multiple concurrent execution hosts.

#### Scenario: Two servers on different ports

- **WHEN** two servers are started on ports 8765 and 9000
- **THEN** each SHALL have its own PID file: `~/.onetool/direct-server-{port}.pid`
- **AND** each SHALL have its own log file: `~/.onetool/direct-server-{port}.log`
- **AND** stopping one host SHALL not affect the other
