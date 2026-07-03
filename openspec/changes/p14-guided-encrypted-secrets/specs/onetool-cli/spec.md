## MODIFIED Requirements

### Requirement: Init Guided Setup

The `onetool init` command SHALL guide users through selective config file materialisation rather
than bulk-copying all templates, and SHALL always materialise `secrets.yaml`, offering a guided
encrypted-secrets setup that never leaves a plaintext secret value on disk.

The primary interface is `onetool init` (uses current directory) or `onetool init -c <path>` for
an explicit path. No mandatory flags are required.

`--config` / `-c` uses suffix detection to determine intent:
- Path ending in `.yaml` or `.yml` → treated as the config file path; parent directory is the config dir
- Any other path → treated as the config directory; `onetool.yaml` is written inside it

Existing files in the target directory SHALL be backed up to `<filename>.bak` (or
`<filename>.bak1`, `<filename>.bak2`, etc. to avoid collisions) before being overwritten, and a
warning SHALL be printed.

`secrets.yaml` is materialised through the same checkbox selection UI as the other extensions, but
it is a special case: unlike `prompts.yaml`/`servers.yaml`/`security.yaml`/`diagram.yaml`/
`snippets.yaml` (which are merged into `onetool.yaml` via the `include:` list), `secrets.yaml` is
never added to `include:` — it is a separate, gitignored file loaded only via the `--secrets` CLI
flag, and merging it into `include:` would expose secret values as top-level config keys.

#### Scenario: Init with no flags (interactive)
- **GIVEN** `onetool init` or `onetool init -c <path>` is run
- **AND** stdin is a TTY
- **WHEN** init runs
- **THEN** it SHALL first prompt the user to confirm or edit the resolved config file path (e.g. `Config file: onetool.yaml`)
  - The default shown is the fully-resolved `config_path`; pressing enter accepts it; typing a new path overrides it
  - Ctrl+C at this prompt cancels without writing any files
- **AND** it SHALL display a checkbox multi-select TUI listing all available extensions:
  - `prompts.yaml`, `servers.yaml`, `security.yaml`, `diagram.yaml`, `snippets.yaml`, `secrets.yaml`
- **AND** materialise only the extensions selected by the user
- **AND** write an `onetool.yaml` whose `include:` list contains only the materialised
  config-include extensions (`prompts.yaml`, `servers.yaml`, `security.yaml`, `diagram.yaml`,
  `snippets.yaml`) — `secrets.yaml`, if selected, SHALL be materialised but SHALL NOT appear in
  `include:`
- **AND** if the user cancels (Ctrl+C) at the checkbox, exit with code 0 without writing any files

#### Scenario: diagram.yaml editable template directory
- **GIVEN** the user selects `diagram.yaml` during init
- **WHEN** init materialises `diagram.yaml`
- **THEN** it SHALL also copy packaged diagram templates into `templates/diagram/` under the config dir
- **AND** if `templates/diagram/` already exists it SHALL be backed up using the standard `.bak` scheme before overwriting

#### Scenario: Conflict handling
- **GIVEN** a file already exists in the target directory
- **WHEN** `onetool init` would overwrite it
- **THEN** the existing file SHALL be renamed to `<filename>.bak` (incrementing to `.bak1`, `.bak2`, etc. if needed)
- **AND** a warning SHALL be printed naming both the original and backup paths
- **AND** the new file SHALL be written to the original path

#### Scenario: Minimal output config
- **GIVEN** the user does not select any extensions during init (or stdin is not a TTY)
- **WHEN** init completes
- **THEN** the generated `onetool.yaml` SHALL contain only `version: 2` with no `include:` section

#### Scenario: secrets.yaml selected without encrypted-secrets setup
- **GIVEN** the user selects `secrets.yaml` in the extensions checkbox
- **AND** declines the "Set up encrypted secrets?" prompt (see below)
- **WHEN** init materialises `secrets.yaml`
- **THEN** it SHALL copy the `secrets-template.yaml` template to `secrets.yaml` in the config dir
  (the same materialisation used by `ensure_ot_dir()`'s first-run path)
- **AND** SHALL `chmod` the file to `0600`
- **AND** SHALL NOT prompt for key/value pairs or call any `ot_secrets` function
- **AND** SHALL NOT add `secrets.yaml` to the generated `onetool.yaml`'s `include:` list

#### Scenario: secrets.yaml selected with encrypted-secrets setup
- **GIVEN** the user selects `secrets.yaml` in the extensions checkbox
- **WHEN** `secrets.yaml` has been materialised
- **THEN** init SHALL prompt "Set up encrypted secrets?" (yes/no, default no)
- **AND** if the user answers yes:
  - it SHALL prompt in a loop for `key` (text) and `value` (masked/password input) pairs, until
    the user submits an empty key to stop
  - it SHALL write each entered pair into `secrets.yaml`
  - it SHALL call `ot_secrets.init()` (or reuse an existing identity if the user confirms reuse)
  - it SHALL call `ot_secrets.encrypt(file=<secrets.yaml path>, backup=False)`
  - it SHALL call `ot_secrets.audit(file=<secrets.yaml path>)` and verify `safe == True` before
    reporting success
  - it SHALL print a success message including the identity's public-key hint
  - at no point after this flow completes SHALL `secrets.yaml` contain a plaintext value for any
    key entered during this step

#### Scenario: Cancel during encrypted-secrets key/value entry
- **GIVEN** the user answered yes to "Set up encrypted secrets?"
- **WHEN** the user cancels (Ctrl+C) during key/value entry
- **THEN** init SHALL stop the secrets step without calling `ot_secrets.init()`/`encrypt()`
- **AND** any key/value pairs already written to `secrets.yaml` before the cancellation SHALL
  remain as plain values (not silently encrypted, not silently discarded) and the terminal output
  SHALL tell the user their `secrets.yaml` still has unencrypted values pending
  `ot_secrets.encrypt()`

### Requirement: Init Validate Source Reporting

The `onetool init validate` command SHALL report the source of each resolved include.

#### Scenario: Validate shows include sources
- **GIVEN** `onetool init validate` is run
- **AND** some includes are user-owned and some use package defaults
- **WHEN** validation output is displayed
- **THEN** each include SHALL be listed with its source tag:
  - `[user]` — loaded from the config dir (`config_path.parent/<path>`)
  - `[default]` — loaded from `global_templates/<path>`
  - `[missing]` — listed in `include:` but not found in either location
  - `[absolute]` — resolved from an absolute path
  - `[not listed]` — not in `include:`, not loaded
- **AND** the resolved file path SHALL be shown for each loaded include

#### Scenario: Validate suggests materialisation
- **GIVEN** an include using a package default (`[default]` source)
- **WHEN** validation output is shown
- **THEN** it SHALL include a hint suggesting how to materialise the file locally to customise it
