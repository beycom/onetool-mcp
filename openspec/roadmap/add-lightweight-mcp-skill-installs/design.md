## Context

The published `onetool-mcp` wheel currently owns the `onetool` console script,
the MCP runtime, base packs, optional pack packages, and a large unconditional
dependency set. Python extras only add dependencies, so a new `[skill]` extra
cannot subtract the existing MCP requirements. A real skill-only install therefore
requires the published base distribution to become a lightweight facade and the
MCP and Skill implementations to cross separately installable wheel boundaries.

The separate `oneskill` repository is a pre-v1 product with approximately 9,600
lines of source, 6,500 lines of tests, a broad CLI, its own configuration and
lockfile contracts, and multiple OpenSpec capabilities. It is still evolving and
must remain its own source of truth until a stable v1 tag exists. This roadmap
change defines the eventual package and CLI integration without copying a mutable
pre-v1 snapshot.

The existing shell and PowerShell bootstrap scripts install `[all]`, initialize an
MCP configuration, and print MCP client configuration. A skill-only installation
does not need those MCP-specific steps, so component selection must occur before
post-install initialization.

## Goals / Non-Goals

**Goals:**

- Keep `onetool-mcp` as the only distribution users need to name in documented
  `uv tool install` commands.
- Make bare `onetool-mcp` a small facade and make `[mcp]` and `[skill]` genuinely
  independent dependency selections.
- Compose installed components into one `onetool` CLI without competing console
  scripts or import-time optional-dependency failures.
- Preserve `[util]` and `[dev]` as MCP pack selections and provide an explicit
  full `[mcp,util,dev,skill]` composition.
- Make the bootstrap choose a useful component set interactively and behave
  deterministically without a terminal.
- Gate the source merge on a stable `oneskill` v1 tag, then make this repository
  canonical for the integrated Skill component.
- Preserve the stable v1 Skill behavior under `onetool skill` while making clean,
  intentional naming changes without compatibility aliases.

**Non-Goals:**

- Do not copy, vendor, or track a pre-v1 `oneskill` snapshot.
- Do not make Python extras subtract or conditionally suppress base dependencies.
- Do not implement post-install hooks or make `onetool` mutate its own environment.
- Do not expose skill building or installation through MCP tools.
- Do not make `util` or `dev` usable without the MCP runtime.
- Do not fold the existing `[scrape]` browser dependency into the new `[all]`
  definition; it remains separately selected unless a later change modifies it.
- Do not preserve the `oneskill` executable or removed names as aliases.

## Decisions

### Decision: Publish a facade and separately packaged components

The root `onetool-mcp` distribution becomes the lightweight facade. It owns the
`onetool` console script, component discovery, root help, `--version`, and
component diagnostics. Its required dependencies are limited to the CLI substrate.

The monorepo contains separately built component distributions:

```text
onetool-mcp                 # public facade and console script
packages/onetool-mcp-runtime
packages/onetool-skill
packages/onetool-pack
```

`onetool-mcp-runtime` owns the current `ot`, `ottools`, MCP-facing CLI commands,
and the optional `otutil` and `otdev` pack dependencies. `onetool-skill` owns the
merged stable Skill implementation. Component wheels do not declare their own
`onetool` console scripts.

Alternative considered: keep the runtime source in the facade and move only its
dependencies behind `[mcp]`. Rejected because installers do not record which
extras were selected, so runtime command registration would have to infer state
from incidental imports and partial environments.

Alternative considered: publish `onetool-skill` as the only lightweight user
entry point. Rejected because the required public installation surface is
`onetool-mcp[skill]` and two distributions must not compete for the `onetool`
executable.

### Decision: Compose commands through a narrow component entry point

The facade discovers a private, versioned entry-point group for installed OneTool
components. Each component returns metadata plus a Typer application or explicit
root command registrations. Registration is deterministic, duplicate component or
command names fail closed, and a component API-version mismatch produces an
actionable reinstall/upgrade error.

The MCP component contributes `serve`, `init`, `direct`, `kb`, and the temporary
bare-root MCP callback. The Skill component contributes only the `skill` group.
Facade construction must not import FastMCP, MCP, OpenAI, Pillow, or Skill modules
when their component is absent.

Alternative considered: hard-coded `try/except ImportError` registration. Rejected
because it confuses missing components with broken component imports and can hide
packaging defects.

### Decision: Make extras a dependency-closure contract

The facade metadata expresses these closures:

```text
[mcp]   -> matching onetool-mcp-runtime
[skill] -> matching onetool-skill
[util]  -> matching onetool-mcp-runtime[util]
[dev]   -> matching onetool-mcp-runtime[dev]
[all]   -> onetool-mcp[mcp,util,dev,skill]
```

`[util]` and `[dev]` transitively install the runtime because their packs cannot
operate without it. An explicit `[mcp,util,dev,skill]` selection remains supported
and resolves duplicate requirements normally. Published facade and component
versions are exactly aligned within a release so a component API cannot drift.

The Skill wheel retains only its stable required dependencies. LLM-assisted Skill
features remain behind a Skill-specific optional dependency that the facade may
expose later only if it is part of the accepted v1 contract.

### Decision: Make bootstrap selection component-aware

When `ONETOOL_EXTRAS` is set, both bootstrap scripts validate and install that
selection without prompting. Otherwise, when a controlling terminal is available,
they offer:

1. MCP (`mcp`, default)
2. Skill (`skill`)
3. MCP + Skill (`mcp,skill`)
4. Complete (`mcp,util,dev,skill`)

The POSIX script reads from the controlling terminal so a documented `curl | sh`
invocation can still prompt; PowerShell uses its host prompt when interactive. If
no terminal is available, the deterministic default is `mcp`.

MCP-containing selections continue through `onetool init`, MCP configuration, and
validation guidance. A Skill-only selection skips all MCP configuration and ends
with `onetool skill --help` and Skill quick-start guidance. A facade-only install
is documented as an advanced manual option, not a bootstrap choice.

Alternative considered: first install the facade and let it install extras into
its own uv tool environment. Rejected because self-modifying environments are
installer-specific, difficult to make atomic, and unnecessary while the bootstrap
already owns package selection.

### Decision: Merge only the stable v1 Skill source and contracts

Implementation begins the Skill import only after the separate repository has an
immutable stable v1 tag and passes its own release checks. The task records the tag
and commit, imports its history into a temporary monorepo prefix, and then relocates
source, tests, docs, and OpenSpec requirements into OneTool-owned locations in the
same change. After merge, this repository is canonical; no ongoing subtree sync or
dual-source development remains.

The complete stable v1 command inventory moves beneath `onetool skill`. The merge
performs final OneTool naming in one pass and deletes old command/config names. It
does not accept old names, probe old paths, or ship migration aliases. Exact file,
environment, and manifest names are fixed after auditing the v1 contracts rather
than freezing pre-v1 names in this roadmap.

### Decision: Verify built-wheel isolation, not only source tests

Packaging acceptance uses clean temporary environments built from release wheels.
The Skill-only environment must run `onetool skill --help`, build, and install
smoke tests while proving MCP runtime distributions and representative heavy
dependencies are absent. The MCP-only environment must serve without the Skill
component. The combined environment must expose both surfaces. Metadata inspection
must confirm the published dependency closures.

### Decision: Release components before the facade

One release version applies to the facade, MCP runtime, Skill component, and
`onetool-pack`. Release automation builds and validates every wheel, publishes
dependency components first, and publishes `onetool-mcp` last. A facade is never
published with references to unavailable component versions.

## Risks / Trade-offs

- [Risk] Bare `onetool-mcp` changes from a working MCP server to a facade. ->
  Mitigation: ship in a major release, make bootstrap/manual docs select `[mcp]`,
  and provide exact component diagnostics from the bare facade.
- [Risk] Splitting the current wheel exposes hidden imports across package
  boundaries. -> Mitigation: add AST/import boundary checks and clean-wheel smoke
  tests before changing release metadata.
- [Risk] A pip/PyPI partial publish leaves the facade unresolvable. -> Mitigation:
  publish components first, verify them from the index, then publish the facade.
- [Risk] Piped interactive installation cannot access a terminal in CI or some
  shells. -> Mitigation: detect a controlling terminal, default to `[mcp]` when
  absent, and keep `ONETOOL_EXTRAS` authoritative.
- [Risk] `oneskill` v1 differs materially from the current repository and invalidates
  roadmap assumptions. -> Mitigation: require a v1 contract audit and update these
  roadmap artifacts before moving the change back to `openspec/changes`.
- [Risk] Moving many Skill specs at once creates gaps or duplicate ownership. ->
  Mitigation: inventory every v1 requirement and test, map each to one OneTool
  capability, and block removal of the source repository until parity passes.
- [Risk] Exact lockstep component versions increase release work. -> Mitigation:
  automate multi-wheel versioning, build, publication order, and index verification.

## Migration Plan

1. Wait for and record the stable `oneskill` v1 tag and commit; rerun the contract,
   dependency, license, and command inventory before implementation.
2. Move this roadmap package back to `openspec/changes`, update any assumptions
   that changed at v1, and verify it is apply-ready.
3. Extract the facade and MCP runtime package boundary while retaining current
   behavior in source-based tests.
4. Add component discovery and wheel-isolation tests, then move required runtime
   dependencies behind `[mcp]` and pack dependencies behind runtime extras.
5. Import the v1 Skill history and relocate its stable implementation, tests,
   specs, and docs; register the `skill` component.
6. Update bootstrap selection, manual installation docs, upgrade guidance,
   generated installer copies, and checksums.
7. Build and test facade-only, MCP-only, Skill-only, MCP + Skill, and complete wheel
   environments on supported Python/platform combinations.
8. Publish internal component wheels first and the breaking facade release last.

Rollback before publication restores the previous single-wheel build. After the
breaking release is published, rollback requires a new release that repins the
facade and components; it must not restore bare-install MCP behavior through a
hidden fallback.

## Open Questions

- What exact OneTool-owned names replace the v1 Skill user config, cache, lockfile,
  environment variable, and manifest-extension names? Decide from the stable v1
  inventory before implementation and update the delta specs without aliases.
- Does stable v1 retain a separate optional LLM dependency, and if so should the
  facade expose it as `skill-llm` or require direct composition with the component
  package? Decide from the v1 dependency contract.
