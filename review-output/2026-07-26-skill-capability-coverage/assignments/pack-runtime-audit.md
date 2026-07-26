# Assignment pack-runtime-audit

Review revision: `528cac463d21f3b510757e106d31ad310591d56b` with the OpenSpec worktree
change recorded in the run plan.

Goal: inventory the distinctive powers, high-value workflows, setup/config dependencies, mutation
boundaries, and verification paths implemented by every built-in pack.

Owned dimensions: `requirements-specs`, `documentation-dx`, `security-privacy`.

Owned scope and primary paths: `pack-runtime`; `src/ottools/`, `src/otutil/tools/`,
`src/otdev/tools/`, and `packages/onetool-pack/src/otpack/`.

Read-only dependency context: shared pack utilities under `src/ot/`, current pack
reference indexes, and the pack-obligation matrix in the proposed OpenSpec design.

Explicit exclusions: final skill ownership/candidate decisions, platform CLI/direct API behavior,
vendored assets, generated files, templates, tests, and fixtures.

Depth and budget: standard static inspection; cover every pack entry point, with deeper attention
to workflow-heavy or high-risk packs.

Allowed commands: static searches, file reads, and Git metadata only.

Return:

1. A pack-by-pack capability inventory with exact path:line evidence.
2. Capabilities or decision points missing from the proposed pack-obligation matrix.
3. Setup, safety, and verification concerns that a skill or help topic must teach.
4. Cross-scope handoffs for platform or skill-system conclusions.
5. A coverage receipt listing inspected entry points, omissions, and confidence.

Rules: do not modify files, do not delegate, do not run repository code/tests/builds, and do not use
the network. Report only evidence in the owned scope.

## Draft outcomes and handoffs

- No conventional defect issue was drafted inside the pack implementations.
- The proposed pack-obligation matrix needs concrete corrections for 23 pack areas, including:
  actual Forge `create_ext`/`validate_ext`; the complete secrets/timer/memory/local-history
  lifecycles; Brave video and batches; Tavily `research` rather than nonexistent `answer`; exact
  architecture round-trip/generation semantics; knowledge MCP versus CLI administration;
  Context7 direct auto-resolution; DB `read_only=False` plus AUTOCOMMIT; diagram remote/privacy and
  async behavior; browser helper lifecycles; and beta console exclusion.
- Cross-scope handoffs: knowledge CLI administration belongs in skill synthesis; browser packs need
  typed proxy compatibility requirements; configurable architecture render commands need
  conditional CLI requirements; remote-data/privacy boundaries need a consistent catalog policy;
  image examples need canonical pack-name correction; beta console examples need documentation-only
  correction.
- Full structured evidence was returned to the orchestration agent and incorporated into the
  review synthesis.

## Coverage receipt

- Assignment: `pack-runtime-audit`
- Inspected: exported entry points and relevant implementation modules for `console`, `ot_forge`,
  `ot_image`, `ot_llm`, `ot_secrets`, `ot_servers`, `ot_timer`, `ot_context`, `brave`, `convert`,
  `excel`, `file`, `ground`, `knowledge`, `mem`, `tavily`, `arch`, `chrome_util`, `context7`, `db`,
  `diagram`, `whiteboard`, `localhist`, `package`, `play_util`, `ripgrep`, and `webfetch`.
- Checks run: static source searches and file inspection only; no repository-controlled commands,
  tests, builds, or network access.
- Issues drafted: none; matrix corrections and cross-scope gaps handed to
  `skill-coverage-synthesis`.
- Handoffs: core `ot` and platform behavior to `platform-surface-audit`; knowledge CLI and final
  skill boundaries to `skill-coverage-synthesis`.
- Follow-up inspected: all 16 files under `packages/onetool-pack/src/otpack/`, including config,
  dependency metadata, HTTP/auth, batches, embeddings, caching/client lifecycle, paths/security,
  project state, logging, text, install hints, and validation helpers.
- `otpack` is a pack-author SDK, not an agent-callable namespace; no standalone skill is warranted.
  Its behavior belongs in pack-development guidance, setup/help readiness, and the owning
  memory/knowledge/search/filesystem skills. HMAC belongs with Direct API documentation.
- The follow-up also found explicitly documented duplicated logging behavior that needs a DRY drift
  check or shared source.
- Not inspected: core `ot`, CLI/direct API, tests/fixtures, and generated references by assignment
  boundary.
- Coverage confidence: high for exported pack surfaces; medium for handed-off platform workflows.
