# direct-run Specification

## Purpose

Defines the `onetool direct run` command for direct tool execution from the shell. Supports in-process execution and optional routing to a running execution server.

---

## Requirements

### Requirement: direct run command

The system SHALL provide `onetool direct run COMMAND` for direct tool execution from the shell.

`COMMAND` is a positional argument (not a flag). Passing `-` as the command reads from stdin. Passing a path to an existing `.py` file reads the file contents and executes them.

Flags:
- `--config`/`-c` — path to `onetool.yaml`; required when running in-process (no server)
- `--secrets`/`-s` — path to secrets file; optional
- `--format`/`-f` — output format: `json_h` (default), `json`, `yml`, `yml_h`, `raw`
- `--no-host` — skip server auto-detect, always run in-process
- `--sanitize` — enable output sanitization (default: off; use when feeding output to an AI pipeline)
- `--timeout`/`-t` — server request timeout in seconds (overrides `direct.host.timeout` in config)

Secrets resolution for direct commands SHALL follow this precedence:
1. explicit `--secrets`
2. `OT_SECRETS_FILE` environment variable
3. `<config_dir>/secrets.yaml` when `--config` is provided and the file exists
4. none

The format is injected into the execution namespace as `__format__` before the command runs, so the executor serialises the result with the chosen mode. Exit code communicates success/failure; no envelope wrapper is added around the result.

#### Scenario: Basic execution

- **WHEN** `onetool direct run -c onetool.yaml "ot.debug()"` is run
- **THEN** the command SHALL execute and print the result to stdout
- **AND** exit with code 0

#### Scenario: Positional command — no flag needed

- **WHEN** `onetool direct run "brave.search(query='test')"` is run
- **THEN** the command string SHALL be accepted as a positional argument without any `-C` or `--command` flag

#### Scenario: Stdin via dash

- **WHEN** `echo "ot.debug()" | onetool direct run -c onetool.yaml -` is run
- **THEN** the command SHALL be read from stdin and executed
- **AND** the result SHALL be printed to stdout

#### Scenario: .py file path

- **WHEN** `onetool direct run -c onetool.yaml script.py` is run and `script.py` exists
- **THEN** the file contents SHALL be read and executed as the command
- **AND** non-existent paths with `.py` extension SHALL be treated as literal command strings

#### Scenario: Default format (json_h)

- **WHEN** `onetool direct run -c onetool.yaml "ot.debug()"` is run with no `--format`
- **THEN** the result SHALL be serialised as human-readable JSON (2-space indent)
- **AND** no success/duration envelope SHALL wrap the output

#### Scenario: Raw format

- **WHEN** `onetool direct run -c onetool.yaml "ot.debug()" --format raw` is run
- **THEN** the raw result string SHALL be printed to stdout with no serialisation

#### Scenario: JSON compact format

- **WHEN** `onetool direct run -c onetool.yaml "ot.debug()" --format json` is run
- **THEN** output SHALL be compact JSON (no whitespace)

#### Scenario: YAML format

- **WHEN** `onetool direct run -c onetool.yaml "ot.debug()" --format yml` is run
- **THEN** output SHALL be YAML

#### Scenario: Invalid format — exit code 2

- **WHEN** `--format` is set to an unsupported value (e.g. `text`, `yaml`)
- **THEN** the command SHALL exit with code 2 and print an error listing valid values

#### Scenario: Sanitize flag

- **WHEN** `onetool direct run --sanitize -c onetool.yaml "ot.debug()"` is run
- **THEN** output sanitization SHALL be applied (boundary tags, trigger neutralisation)
- **AND** without `--sanitize`, sanitization SHALL be off by default

#### Scenario: Tool execution error — exit code 1

- **WHEN** the executed command raises an error during tool execution
- **THEN** the error message SHALL be printed to stderr
- **AND** the process SHALL exit with code 1

#### Scenario: Config error — exit code 2

- **WHEN** `--config` path does not exist or the YAML is invalid
- **THEN** an error message SHALL be printed to stderr
- **AND** the process SHALL exit with code 2

#### Scenario: Missing secrets file — exit code 2

- **WHEN** `--secrets` path is provided but does not exist
- **THEN** an error message SHALL be printed to stderr
- **AND** the process SHALL exit with code 2

#### Scenario: Environment-provided secrets path missing — exit code 2

- **WHEN** `OT_SECRETS_FILE` points to a non-existent file
- **THEN** an error message SHALL be printed to stderr
- **AND** the process SHALL exit with code 2

### Requirement: direct run server routing

Without `--no-host`, `onetool direct run` SHALL probe for a running execution server on the configured port before executing in-process.

#### Scenario: Server running — routes to server

- **WHEN** an execution server is running on the configured port
- **AND** `onetool direct run "ot.debug()"` is run without `--no-host`
- **THEN** the command string (with `__format__` and `__sanitize__` prepended) SHALL be sent to the server via HTTP POST `/run`
- **AND** the server's result SHALL be printed to stdout

#### Scenario: Local host context mismatch — restart to sync

- **GIVEN** routing target is local host (`127.0.0.1`)
- **AND** a running host exists with different `config` or `secrets` context than the current direct run request
- **WHEN** `onetool direct run ...` is executed
- **THEN** the CLI SHALL restart the local host with the requested context before sending the command
- **AND** routing SHALL proceed to the restarted host

#### Scenario: Server not running — runs in-process

- **WHEN** no execution server is running on the configured port
- **AND** `onetool direct run -c onetool.yaml "ot.debug()"` is run without `--no-host`
- **THEN** the command SHALL execute in-process
- **AND** no error SHALL be reported about the missing server

#### Scenario: direct.host.enabled true — auto-starts server

- **GIVEN** `onetool.yaml` contains `direct.host.enabled: true`
- **WHEN** `onetool direct run -c onetool.yaml "ot.debug()"` is run and no server is running
- **THEN** the server SHALL be auto-started in the background before routing

#### Scenario: direct.host.enabled false — no auto-start

- **GIVEN** `onetool.yaml` contains `direct.host.enabled: false`
- **WHEN** `onetool direct run "ot.debug()"` is run and no server is running
- **THEN** the command SHALL execute in-process
- **AND** the CLI SHALL NOT auto-start a server

#### Scenario: --no-host skips probe

- **WHEN** `onetool direct run -c onetool.yaml --no-host "ot.debug()"` is run
- **THEN** no TCP probe SHALL be performed
- **AND** the command SHALL always execute in-process regardless of server state

#### Scenario: --timeout overrides config

- **WHEN** `onetool direct run --timeout 120 "ot.debug()"` is run routing to a server
- **THEN** the HTTP request timeout SHALL be 120 seconds regardless of `direct.host.timeout` in config
