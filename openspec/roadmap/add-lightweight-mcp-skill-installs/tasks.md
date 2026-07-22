## 1. Stable Skill v1 Gate

- [ ] 1.1 Verify that `/Users/gavin/01-work-thor/projects/group-hobby/oneskill` has
  an immutable stable v1 tag, record its tag and commit in the design, and stop the
  change without importing source if the gate is not satisfied.
- [ ] 1.2 Run the tagged Skill repository's release checks and inventory its
  license, required and optional dependencies, console commands, configuration and
  state names, manifest extensions, generated files, tests, docs, and OpenSpec
  requirements.
- [ ] 1.3 Resolve the design's Skill naming and optional-LLM questions from the v1
  inventory, update the proposal/design/delta specs, and validate that no legacy
  aliases or fallback paths are specified.
- [ ] 1.4 Confirm both repositories have clean or explicitly checkpointed
  worktrees before history import, preserving unrelated user changes.

## 2. Facade and Component Packaging

- [ ] 2.1 Add the lightweight facade package that owns the `onetool` console
  script, version output, root help, and installed-component diagnostics, with unit
  tests that run without MCP or Skill dependencies importable.
- [ ] 2.2 Define the private versioned component entry-point contract and implement
  deterministic discovery, duplicate rejection, API-version validation, and broken
  component diagnostics with focused unit tests.
- [ ] 2.3 Create the `onetool-mcp-runtime` workspace distribution and move the
  current MCP runtime packages and package data behind its wheel boundary without
  changing runtime behavior.
- [ ] 2.4 Register MCP CLI commands and the root MCP callback from the runtime
  component, preserving current serve, init, direct, kb, transport, logging, and
  shutdown integration tests.
- [ ] 2.5 Move current unconditional runtime dependencies into the runtime
  distribution and define facade `[mcp]`, `[util]`, `[dev]`, and `[all]` dependency
  closures with matching component versions.
- [ ] 2.6 Add import-boundary and package-metadata tests proving the facade can be
  imported without runtime packages and that runtime packages do not own a second
  `onetool` console script.

## 3. Stable Skill Source Merge

- [ ] 3.1 Import the recorded stable v1 Skill Git history into a temporary
  monorepo prefix and record its upstream provenance and license without copying
  any later pre-release worktree changes.
- [ ] 3.2 Create the `onetool-skill` workspace distribution, relocate the stable
  source and package data, and apply the approved OneTool package/module names.
- [ ] 3.3 Adapt the stable Typer application into a component-provided `skill`
  group so every accepted v1 command is reachable beneath `onetool skill` and no
  component console script is installed.
- [ ] 3.4 Apply the approved OneTool configuration, cache, lockfile, environment,
  and manifest-extension names; delete the old discovery and validation paths
  without aliases or migration fallbacks.
- [ ] 3.5 Relocate and adapt the stable Skill unit, integration, behavioral, and
  packaging tests under the matching OneTool package test root while preserving
  marker discipline.
- [ ] 3.6 Map every accepted stable Skill OpenSpec requirement to one canonical
  OneTool capability, merge missing detailed requirements into main or delta
  specs, and remove duplicate nested specification ownership.
- [ ] 3.7 Relocate stable Skill user and developer documentation into the OneTool
  documentation hierarchy, update command examples to `onetool skill`, and remove
  standalone-project release and installation instructions.
- [ ] 3.8 Remove the temporary import prefix and all obsolete `oneskill`
  executable, module, documentation, config, environment, and package references;
  add negative tests proving removed names fail normally.

## 4. Interactive Bootstrap Installation

- [ ] 4.1 Implement and unit-test shared selection validation for `mcp`, `skill`,
  `util`, `dev`, and supported compositions, including rejection of empty,
  duplicate, and unknown `ONETOOL_EXTRAS` values.
- [ ] 4.2 Update `scripts/install.sh` to prompt through the controlling terminal,
  select MCP by default, honor non-interactive overrides, and branch MCP versus
  Skill post-install guidance; add scripted shell tests for every selection.
- [ ] 4.3 Update `scripts/install.ps1` with equivalent interactive,
  non-interactive, validation, and post-install behavior; add PowerShell tests for
  every selection.
- [ ] 4.4 Regenerate the docs-domain installer copies and SHA-256 files from the
  canonical scripts and verify byte identity and checksum validation.

## 5. Documentation and Upgrade Contract

- [ ] 5.1 Update README, installation, quick-start, CLI, tool-extra, and release
  documentation to show `[mcp]`, `[skill]`, `[mcp,skill]`, and
  `[mcp,util,dev,skill]`, identifying bare `onetool-mcp` as facade-only.
- [ ] 5.2 Add major-release upgrade guidance that requires existing MCP users to
  reinstall with `[mcp]` or a composition containing it and does not offer a
  bare-install compatibility fallback.
- [ ] 5.3 Update OpenSpec indexes and canonical developer package/CLI/release maps
  for the facade, runtime, Skill, and `onetool-pack` ownership boundaries.

## 6. Installed-Wheel and Release Verification

- [ ] 6.1 Build all workspace wheels and inspect wheel contents, entry points, and
  `Requires-Dist` metadata for exact component ownership and version pins.
- [ ] 6.2 In clean temporary environments, verify facade-only, MCP-only,
  Skill-only, MCP + Skill, utility, developer, and complete installation matrices,
  including explicit absence assertions for unselected component dependencies.
- [ ] 6.3 Run installed-wheel MCP startup and transport smoke tests plus stable
  Skill build and install smoke tests without relying on repository `pythonpath`.
- [ ] 6.4 Update release automation to version and build all component wheels,
  publish dependency components first, verify index availability, and publish the
  `onetool-mcp` facade last.
- [ ] 6.5 Run `just check`, strict documentation build, installer tests, package
  boundary checks, and release dry-run; record passing evidence before marking the
  change complete.
