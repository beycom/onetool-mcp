# skill-ot-ref Delta

New capability: the content and generation contract for the ot-ref skill delivered from the
top-level `skills/ot-ref/` layout established by `p11-skills-standard-layout`.

## ADDED Requirements

### Requirement: Trigger-Forward Description

The ot-ref skill's frontmatter `description` SHALL lead with WHEN to load it (before the agent's
first OneTool call) and then WHAT it carries, so harness trigger-matching fires early rather than
on failure.

#### Scenario: Description leads with use-when
- **GIVEN** `skills/ot-ref/SKILL.md`
- **WHEN** the frontmatter is read
- **THEN** the `description` SHALL begin with "Use when calling any OneTool pack tool"
- **AND** SHALL mention the pack map, call syntax, kwarg/alias resolution, the command index, recovery, and large-result handling

#### Scenario: Body invites early loading
- **GIVEN** the SKILL.md body
- **WHEN** its opening lines are read
- **THEN** they SHALL instruct loading the skill when working with OneTool tools
- **AND** SHALL NOT describe the skill as optional or say base instructions are sufficient (the old opener actively discouraged activation)

### Requirement: Codex Sidecar Allows Implicit Invocation

The skill SHALL ship a Codex sidecar `skills/ot-ref/agents/openai.yaml` whose policy allows
implicit invocation.

#### Scenario: Sidecar present and permissive
- **GIVEN** `skills/ot-ref/agents/openai.yaml`
- **WHEN** parsed
- **THEN** it SHALL NOT set `allow_implicit_invocation: false`
- **AND** the file SHALL record (comment) that the skill must load before the first OneTool call

### Requirement: Body Structured by Trigger-Time

The SKILL.md body SHALL carry only the always-relevant, cheap content (call conventions, engine
forgiveness, generated pack map, discovery, how to grep the command index, recovery pointers,
large-result handling, output-control summary); deep-dive material SHALL live in
`reference/recovery.md` and be pulled on demand.

#### Scenario: Deep dive split out
- **GIVEN** the skill directory
- **WHEN** listed
- **THEN** `reference/recovery.md` SHALL exist containing the fail-first recovery flow, param-prefix detail, proxy recovery, security boundaries, run-vs-local-script decision, output dunders, and ctx navigation
- **AND** SKILL.md SHALL link to it rather than inlining that material

#### Scenario: Primary handle idiom
- **GIVEN** the skill content
- **WHEN** large-result handling is documented
- **THEN** `ot.result(handle=...)` SHALL be presented as the primary idiom available on every install
- **AND** `ctx.toc/read/slice/grep/query/ask` SHALL be presented as the richer navigation available with the `[util]` extra

### Requirement: Generated Pack Map

The pack-map section of SKILL.md SHALL be generated at build time between explicit markers, never
hand-maintained, and SHALL show each pack's declared aliases.

#### Scenario: Marker-delimited generation
- **GIVEN** SKILL.md
- **WHEN** the docs generation step runs
- **THEN** the content between `<!-- packmap:begin` and `<!-- packmap:end -->` SHALL be rewritten from the live registry (pack names, aliases, one-line descriptions)

#### Scenario: Aliases visible
- **GIVEN** a pack with declared aliases (e.g. `whiteboard` with `wb`)
- **WHEN** the pack map is generated
- **THEN** the entry SHALL show the aliases next to the pack name (e.g. `**whiteboard** (wb, excalidraw)`)

### Requirement: Greppable Command Index Ships With the Skill

The full tool signature index SHALL be generated into `skills/ot-ref/reference/tool-index.md` by
the same generator that produces `docs/reference/tools/tool-index.md`, in the one canonical
format `pack.tool(compact_args)  # description` grouped under `## pack, alias` headings. It is a
file the agent greps with its own tools — it SHALL NOT be loaded into context wholesale by the
skill body or served as inline skill content.

#### Scenario: Generated alongside docs copy
- **GIVEN** the docs generation step runs
- **WHEN** it completes
- **THEN** `skills/ot-ref/reference/tool-index.md` SHALL exist and be byte-identical to `docs/reference/tools/tool-index.md`

#### Scenario: Staleness guarded
- **GIVEN** the docs-consistency check (`scripts/check_docs_registry.py` or the generated-blocks sync check)
- **WHEN** the skill copy differs from a fresh generation
- **THEN** the check SHALL fail

#### Scenario: Skill body teaches grep, not load
- **GIVEN** SKILL.md
- **WHEN** the command-index section is read
- **THEN** it SHALL describe the one-liner format and give grep examples against `reference/tool-index.md`
- **AND** SHALL instruct the agent not to read the whole file into context
