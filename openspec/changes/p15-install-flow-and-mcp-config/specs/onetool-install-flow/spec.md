## ADDED Requirements

### Requirement: Bootstrap installer script

OneTool SHALL ship a POSIX shell bootstrap script (`scripts/install.sh`) and a PowerShell bootstrap script (`scripts/install.ps1`) that wrap `uv` — never replace it — and collapse the install → init → mcp-config sequence into a single documented command. PyInstaller-style single-binary packaging is explicitly rejected: OneTool's worker-pool tools resolve PEP 723 dependencies via `uv run` at runtime (`src/ot/executor/worker_pool.py:220-222`), so a frozen binary would have no `uv` available and would break every worker-pool pack (db, excel, etc.) plus `ot_forge` extensions; a frozen binary also cannot express the optional-extras model and would carry a per-platform sign/notarize burden the bootstrap avoids entirely.

Both scripts SHALL, in order:
1. Detect the host platform.
2. Check whether `uv` is already on `PATH`; if not, install it using `uv`'s own official installer (`curl -LsSf https://astral.sh/uv/install.sh | sh` on macOS/Linux, `irm https://astral.sh/uv/install.ps1 | iex` on Windows) and make it available on `PATH` for the remainder of the script's execution.
3. Run `uv tool install 'onetool-mcp[<extras>]'`, where `<extras>` defaults to `all` and is overridable via an `ONETOOL_EXTRAS` environment variable.
4. Run `onetool init --config <config-dir>`, where `<config-dir>` defaults to a platform-appropriate home-relative path (`~/.onetool`) and is overridable via an `ONETOOL_CONFIG_DIR` environment variable.
5. Run `onetool init mcp-config --config <config-dir>/onetool.yaml` and let its output pass through to the user's terminal.
6. Print a closing message pointing at `onetool init validate` as the verification step, and noting that step 4 ran non-interactively (because script stdin is consumed by the `curl | sh` / `irm | iex` pipe) — so extension selection and guided secrets setup require re-running `onetool init --config <config-dir>` interactively in a normal terminal afterward.

`uv tool install` SHALL remain the documented manual installation path in all docs; the bootstrap is presented as the *recommended* default, not a replacement for the manual path.

#### Scenario: uv already installed
- **GIVEN** `uv` is already on `PATH`
- **WHEN** `scripts/install.sh` (or `.ps1`) runs
- **THEN** it SHALL skip the uv installer step
- **AND** it SHALL proceed directly to `uv tool install 'onetool-mcp[all]'`

#### Scenario: uv missing
- **GIVEN** `uv` is not on `PATH`
- **WHEN** `scripts/install.sh` (or `.ps1`) runs
- **THEN** it SHALL install `uv` via `uv`'s official installer before attempting `uv tool install`
- **AND** the script's own `PATH` SHALL be updated so the subsequent `uv tool install` call succeeds in the same process

#### Scenario: Default extras
- **GIVEN** `ONETOOL_EXTRAS` is not set
- **WHEN** the bootstrap script runs
- **THEN** it SHALL run `uv tool install 'onetool-mcp[all]'`

#### Scenario: Overridable extras
- **GIVEN** `ONETOOL_EXTRAS=util` is set in the environment
- **WHEN** the bootstrap script runs
- **THEN** it SHALL run `uv tool install 'onetool-mcp[util]'`

#### Scenario: Non-interactive init during bootstrap
- **GIVEN** the bootstrap script is invoked via `curl -LsSf <url> | sh`
- **WHEN** the script's `onetool init` step runs
- **THEN** `onetool init` SHALL observe a non-TTY stdin and take the non-interactive path (writing a minimal `onetool.yaml` per the `onetool-cli` "Minimal output config" / idempotent-re-run contract)
- **AND** the closing message SHALL tell the user to re-run `onetool init` interactively afterward for extension and secrets setup

#### Scenario: mcp-config printed at the end of bootstrap
- **WHEN** the bootstrap script completes successfully
- **THEN** the last thing printed SHALL be the output of `onetool init mcp-config` for the config path just initialized

### Requirement: Installer distribution and integrity

The bootstrap scripts SHALL be distributed from two locations that both resolve to the same versioned content:
- The official docs domain, for the primary documented one-liner (`https://onetool.beycom.online/install.sh` / `.../install.ps1`).
- A git-tag-pinned GitHub raw URL (`https://raw.githubusercontent.com/beycom/onetool-mcp/<tag>/scripts/install.sh`), for reproducible/CI installs pinned to a specific released version.

A published sha256 checksum file SHALL accompany each script (`install.sh.sha256`, `install.ps1.sha256`) at the same docs-domain location, and installation docs SHALL document the inspect-then-verify-then-run sequence (download the script, `shasum -a 256 -c` against the published checksum, then execute) as an explicit alternative to piping directly into a shell.

#### Scenario: Docs-domain script matches repo script
- **GIVEN** the docs site has been built and deployed
- **WHEN** `docs/install.sh` is compared to `scripts/install.sh`
- **THEN** the content SHALL be byte-identical (the docs copy is generated from the repo copy, never hand-edited separately)

#### Scenario: Checksum file is generated, not hand-maintained
- **WHEN** the docs build step that copies `scripts/install.sh`/`scripts/install.ps1` into `docs/` runs
- **THEN** it SHALL also (re)generate `docs/install.sh.sha256` and `docs/install.ps1.sha256` from the current script content

#### Scenario: Inspect-first path documented
- **WHEN** a user reads the installation docs
- **THEN** they SHALL find both the direct `curl -LsSf <url> | sh` one-liner and the inspect-first alternative (`curl -LsSf <url> -o install.sh && shasum -a 256 -c install.sh.sha256 && sh install.sh`)

### Requirement: Repeatable first-run command sequence

Documentation SHALL present install → init → mcp-config → validate as a single, explicitly ordered, copy/paste-friendly sequence, with `onetool init validate` as the one documented command that confirms the whole flow succeeded. No additional install wrapper beyond the bootstrap script SHALL be introduced.

#### Scenario: Recommended sequence documented
- **WHEN** a user reads the installation or quickstart docs
- **THEN** they SHALL find the sequence, in order: the bootstrap one-liner (or the manual `uv tool install 'onetool-mcp[all]'` + `onetool init` alternative), `onetool init mcp-config --client <their-client>` (or reading the bootstrap's own printed output), pasting the result into their MCP client, then `onetool init validate --config <path>`
- **AND** each step's expected output or effect SHALL be stated (e.g. what `init validate` prints on success)

#### Scenario: Manual path still documented
- **WHEN** a user reads the installation docs
- **THEN** `uv tool install 'onetool-mcp[<extras>]'` (with `onetool init` and `onetool init mcp-config` run manually afterward) SHALL still be documented as a supported alternative to the bootstrap script

#### Scenario: init validate is the documented verification step
- **WHEN** a user reads any doc page that describes finishing setup (quickstart, installation, README)
- **THEN** `onetool init validate --config <path>` SHALL be the command those docs point to for confirming the setup is correct
- **AND** it SHALL be the same command `onetool init` itself prints as its "next step" hint (per the `onetool-cli` "Successful init prints the validate hint" scenario)

#### Scenario: Clean-machine flow produces a working connection with no hand-edited paths
- **GIVEN** a machine with no prior `uv`, `onetool`, or `~/.onetool` directory
- **WHEN** the documented sequence (bootstrap install → `onetool init` → paste `onetool init mcp-config` output into an MCP client → `onetool init validate`) is followed exactly as documented, with no manual path edits
- **THEN** the MCP client SHALL connect to the `onetool` server successfully
- **AND** a first `ot.status()` call through that client SHALL succeed
