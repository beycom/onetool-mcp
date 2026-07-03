## ADDED Requirements

### Requirement: Framework-vs-Product Positioning Disclosure

Public documentation SHALL explicitly contrast OneTool as an installed product against
framework-level building blocks (naming FastMCP Code Mode by name), so a prospective user can
answer "why not just use the framework feature" without leaving the docs.

The contrast SHALL state, at minimum, that: FastMCP is a toolkit for *building* MCP servers;
Code Mode / ProxyProvider / sandbox primitives are ingredients a developer must adopt and expose
themselves; a Claude Code / Cursor / Codex user gets none of that unless someone ships a server
around it; OneTool *is* that shipped server, pre-built, with 200+ curated tools, the
param/alias/snippet forgiveness layer, ctx handles, the prompt + skill that teach an LLM to drive
it, and rich config + security.

#### Scenario: Positioning contrast present in README

- **GIVEN** a user reading `README.md`
- **WHEN** they look for how OneTool differs from a framework capability like FastMCP Code Mode
- **THEN** they SHALL find an explicit "framework feature you'd have to build vs. a product you
  install" contrast that names FastMCP/Code Mode and lists OneTool's pre-built layers (curated
  tools, forgiveness layer, ctx handles, prompt+skill, config/security)

#### Scenario: Positioning contrast present in comparison docs

- **GIVEN** a user reading `docs/learn/comparison.md`
- **WHEN** they look for the product-vs-framework positioning
- **THEN** they SHALL find the same contrast (or a cross-reference to it) alongside the existing
  token/cost benchmark data

### Requirement: MCP Proxy Walkthrough Documentation

`docs/learn/` SHALL contain at least one walkthrough that documents the MCP-proxy story: any
MCP server configured under `servers:` in `onetool.yaml` becomes a callable Python namespace,
tool names are auto-aliased across naming conventions, and connections are controlled at runtime
through `ot_servers` (`srv`).

#### Scenario: Proxy namespace walkthrough exists

- **GIVEN** a user wants to understand how an external MCP server becomes callable as
  `server_name.tool_name(...)`
- **WHEN** they read `docs/learn/`
- **THEN** they SHALL find a walkthrough showing a `servers:` config entry and the resulting
  Python-namespace call, distinct from the tool-pack reference pages

#### Scenario: Name-aliasing documented with examples

- **GIVEN** a user calls a proxied tool using a different naming convention than the upstream
  server exposes (e.g. `listRepositories()` vs `list_repositories()` vs `list-repositories`)
- **WHEN** they read the proxy walkthrough
- **THEN** they SHALL find at least one worked example showing the same proxied call succeeding
  under snake_case, kebab-case, and camelCase spellings

#### Scenario: Runtime server control documented

- **GIVEN** a user wants to enable, disable, restart, or check the status of a configured proxy
  server without restarting OneTool
- **WHEN** they read the proxy walkthrough
- **THEN** they SHALL find the `ot_servers` (`srv`) tools (`enable`, `disable`, `restart`,
  `status`) documented with example calls

#### Scenario: chrome_util/play_util framed as proxy companions

- **GIVEN** a user reads the proxy walkthrough or the `chrome_util`/`play_util` reference pages
- **WHEN** they look for the relationship between OneTool's annotation helpers and the underlying
  proxied browser MCP server (`chrome_devtools`/`playwright`)
- **THEN** they SHALL find `chrome_util`/`play_util` explicitly described as thin companions over
  the proxy manager (the `server=` override pattern), meant to be used alongside the proxied
  server's own tools, not as a replacement for them

### Requirement: Capability Demonstration Content

OneTool SHALL ship a set of scripted, runnable demonstrations under `docs/learn/demos/`, each
built around one undersold capability, driven by `onetool direct run` invocations, and narrated
through a proxied voice MCP server. Each demo SHALL be able to run start-to-finish on a fresh
`[all]`-extras install.

#### Scenario: Demo directory exists with required launch scenarios

- **GIVEN** a user or release reviewer browses `docs/learn/demos/`
- **WHEN** they look for the launch-required demonstrations
- **THEN** they SHALL find runnable scripts for at least the three launch-priority scenarios: the
  forgiveness demo, the codebase-to-live-whiteboard demo, and the "we just committed our secrets
  file" demo

#### Scenario: Demo runs start-to-finish on a fresh install

- **GIVEN** a fresh `uv tool install 'onetool-mcp[all]'` environment with `onetool init` completed
- **WHEN** a demo script under `docs/learn/demos/` is executed
- **THEN** every `onetool direct run` invocation in the script SHALL exit `0`
- **AND** the script SHALL require no manual intervention beyond the documented one-time setup
  (starting the OneTool MCP process and registering the narrator MCP server)

#### Scenario: Demos are narrated through a proxied MCP server

- **GIVEN** a demo script that narrates its steps
- **WHEN** the script speaks a narration line
- **THEN** it SHALL do so by calling a proxied MCP server's tool (not a local/native TTS call
  outside OneTool), demonstrating the proxy story from the MCP Proxy Walkthrough requirement

#### Scenario: Demos double as manual release tests

- **GIVEN** a release reviewer runs every script under `docs/learn/demos/`
- **WHEN** all scripts complete without a non-zero exit code
- **THEN** that run SHALL constitute a passing manual release check for the capabilities each
  demo exercises
