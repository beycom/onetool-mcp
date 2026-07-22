## Why

`onetool-mcp` currently installs the complete MCP runtime before optional extras are
considered, so it cannot provide a lightweight skill-only installation. OneTool
needs a composable package boundary before the evolving `oneskill` project can be
merged after its v1 release without forcing skill users to install FastMCP, MCP,
LLM, image, and server dependencies.

## What Changes

- **BREAKING** Make the base `onetool-mcp` distribution a lightweight CLI facade;
  a working MCP server is installed with `onetool-mcp[mcp]` rather than the bare
  distribution.
- Add independently selectable `[mcp]` and `[skill]` extras. `[skill]` installs the
  OneTool Skill CLI and its dependencies without the MCP runtime, while combined
  extras install both components into one `onetool` command.
- Keep `[util]` and `[dev]` as MCP pack groups that include the MCP component they
  require. Define `[all]` as the full `[mcp,util,dev,skill]` composition.
- Add component-aware CLI help and diagnostics so a facade-only or partial install
  reports installed components and exact commands for adding missing components.
- **BREAKING** Change the bootstrap installer's default from `[all]` to `[mcp]` and
  make terminal installs prompt for MCP, Skill, MCP + Skill, or the complete
  composition. Preserve deterministic non-interactive selection through
  `ONETOOL_EXTRAS`.
- After `oneskill` reaches v1, merge its stable implementation, tests, specs, and
  documentation into this repository as the separately packaged skill component
  and expose its complete command surface under `onetool skill`.
- Do not provide legacy `oneskill` command, configuration, environment, or package
  aliases when the v1 merge is performed; final names are decided from the v1
  contract during implementation.

## Capabilities

### New Capabilities

- `component-installation`: Installable facade, MCP, Skill, optional pack, and
  combined-extra behavior, including dependency isolation and component
  diagnostics.
- `skill-management-cli`: Availability and command namespace for the future
  separately packaged OneTool Skill component after upstream `oneskill` v1.

### Modified Capabilities

- `onetool-cli`: Make root help and invocation component-aware and add the
  `onetool skill` command group when the Skill component is installed.
- `onetool-install-flow`: Replace the all-by-default bootstrap with interactive
  component selection and deterministic `[mcp]` non-interactive behavior.
- `serve-skills`: Permit OneTool's optional host CLI component to build and install
  skills while retaining the prohibition on MCP runtime tools that serve or
  install skill content.

## Impact

- Packaging and release: the root `pyproject.toml`, wheel boundaries, workspace
  packages, lockfile, release commands, PyPI publication order, and component
  version compatibility.
- CLI: the lightweight `onetool` facade, MCP command registration, the future
  `onetool skill` group, version reporting, help, and missing-component errors.
- Installation: `scripts/install.sh`, `scripts/install.ps1`, generated docs copies
  and checksums, `ONETOOL_EXTRAS`, manual installation guidance, bootstrap tests,
  and clean-environment verification.
- MCP runtime: current required dependencies move behind `[mcp]`; `[util]` and
  `[dev]` remain meaningful only with the MCP component.
- Skill component: `/Users/gavin/01-work-thor/projects/group-hobby/oneskill` is an
  evolving source reference only until a stable v1 tag exists. No pre-v1 snapshot
  is copied into OneTool.
- Existing users must reinstall with `[mcp]` (or a composition containing it) when
  upgrading to the breaking release.
