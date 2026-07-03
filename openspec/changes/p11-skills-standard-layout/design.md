## Context

OneTool bundles one skill today, `ot-ref`, an "advanced reference" Markdown document covering recovery flows, proxy handling, security boundaries, output controls, and ctx handle navigation. It is served two ways:

1. **Runtime serving** — `ot.skills()`, an MCP tool that lists/retrieves skill Markdown from `src/ot/config/global_templates/skills/*.md` at request time. Implemented twice: the actually-wired copy lives in `src/ot/meta/_skills_services.py` (delegated to via `src/ot/meta/_server_mgmt.py:78-102` → `src/ot/meta/__init__.py`); a second, structurally dead copy lives at `src/ottools/skills.py` (it has no module-level `pack = "..."` attribute, so `tool_loader.py`'s pack-aware execution namespace never surfaces it — confirmed by tracing `build_execution_namespace()` in `src/ot/executor/pack_proxy.py:264-314`, which only iterates `registry.packs`, never the flat `registry.functions` dict a pack-less module lands in). It is exercised only by its own test file, `tests/ottools/unit/tools/test_skills.py`.
2. **Installer** — `ot_forge.install_skills()` (`src/ottools/ot_forge.py:451-540`), which renders `skill_stub.md.j2` and writes per-agent stub files to `.claude/`, `.codex/`, `.opencode/`, `.pi/` using path templates from `src/ot/config/global_templates/skills.md`.

Both predate the now-standard Agent Skills layout: a top-level `skills/<name>/SKILL.md` in the repo, discoverable and installable by third-party tooling (`npx skills add` from vercel-labs/skills, APM, or manual copy). The maintainer ruled (2026-07-03) that both paths are removed cleanly in V3 — this is a breaking window, "deprecated" means deleted, not shimmed.

The current `serve-skills` spec also requires two skills that were never built (`ot-chrome-devtools-mcp`, `ot-playwright-mcp`) and demos a non-existent skill name in `docs/reference/tools/ot_core.md:324` and `src/ottools/skills.py:8`. This change resolves that drift as part of the removal (no replacement skills are added).

## Goals / Non-Goals

**Goals:**
- Ship `ot-ref` at the standard location (`skills/ot-ref/SKILL.md`) as the single source of truth for its content, with a Codex sidecar (`skills/ot-ref/agents/openai.yaml`).
- Remove the runtime-serving and installer tool surface completely — no `ot.skills`, no `ot_forge.install_skills`, no shims, no deprecation warnings that keep the old call working.
- Leave zero stale references: code, specs, docs, tests, and the local `.codex/` working-tree artifact.
- Make the distribution contract externally verifiable (`npx skills add <repo> --list` finds `ot-ref`) without any OneTool-side installer code.

**Non-Goals:**
- Rewriting `ot-ref`'s content (new trigger description, tools-mastery body, command index). That is explicitly `p21-run-contract-and-command-index`'s job — this change moves the file byte-for-byte (frontmatter + body unchanged).
- Adding any new skills (`ot-chrome-devtools-mcp`, `ot-playwright-mcp`, or others).
- Building a OneTool-owned skill installer to replace the removed one. External tooling owns this now, permanently — not a gap to fill later in this change.
- Touching `prompts.yaml`'s three-layer command index design, `_build_pack_summary`, or any other part of the run contract — only the single `ot.skills(name='ot-ref')` line at `prompts.yaml:41` is deleted.

## Decisions

**Decision: Delete `src/ottools/skills.py` outright rather than leaving it as a no-op.**
It is confirmed dead code (no `pack =` attribute, unreachable via `build_execution_namespace()`), so there is no runtime behavior to preserve. Deleting it removes ~165 lines and its dedicated test file with no functional risk. Alternative considered: leave it in place since it's "already dead." Rejected — dead code that references a removed concept (`global_templates/skills/`) is exactly the kind of drift this change is cleaning up, and the acceptance `rg` check for `ottools.skills` requires it gone.

**Decision: Delete the whole `src/ot/meta/_skills_services.py` module, but only the `skills()` function (lines 78-102) from `src/ot/meta/_server_mgmt.py`, not the whole file.**
`_server_mgmt.py` also defines `security()` and `server()`, which are unrelated live tools (`ot.security`, `ot.server`, covered by the `serve-server-management` spec — out of scope for this change). Only `_skills_services.py` is skills-only and can be deleted wholesale.

**Decision: `skills/ot-ref/agents/openai.yaml` sets `allow_implicit_invocation: true`, not `false`.**
The source issue (`wip/release-v3/issues/move-skills-to-standard-repo-layout.md`) proposed `false` (keep `ot-ref` explicit-only). The maintainer overruled this during the report pass: `ot-ref` is meant to be a *proactive* skill — it carries the runtime's underexplained forgiveness (param prefixes, aliases) and, once p21 lands, the greppable command index. A skill that only helps when explicitly asked for defeats that purpose. This is a deliberate reversal of the issue's suggestion, not an oversight — do not "fix" it back to `false`.

**Decision: No `skills.md`/`skills/` compatibility path in `ensure_ot_dir()`.**
Checked `src/ot/paths.py`'s `INIT_TEMPLATE_FILES`/`INIT_TEMPLATE_DIRS` — `skills.md` and `skills/` were never in the explicit copy-to-`.onetool/` allowlist, so `tests/unit/core/test_paths.py`'s existing "SHALL NOT exist" assertions already hold and require no code change. Verified by reading `src/ot/paths.py:32-45`.

**Decision: `docs/reference/tools/index.md` and `docs/reference/tools/tool-index.md` counts must be regenerated/hand-verified, not hand-guessed.**
`tool-index.md` is generated by `scripts/list_tool_inventory.py` (wraps `src/otdev/docsgen/tool_index.py`); `index.md`'s pack/tool counts are validated (not auto-fixed) by `scripts/check_docs_registry.py`. Removing two tools (`ot.skills`, `ot_forge.install_skills`) changes the `ot` and `ot_forge` pack counts and the total header count. Tasks below require running `just docs-sync` (which chains both scripts) rather than hand-editing a guessed number, because the exact total depends on the state of other in-flight packs.

## Risks / Trade-offs

- **[Risk] Deleting `src/ottools/ot_forge.py:367-540` leaves unused imports** (`cast`, `Any` from `typing`; `cache`, `get_effective_cwd` from `otpack`) since every use site of those four names is inside the deleted range (verified by grep — `Path`, `LogSpan`, `ast`, `fnmatch`, `re`, `get_config_dir` are all used elsewhere and must stay). → Mitigation: tasks.md calls out the exact import-line edit; `ruff` (via `just lint`) will also catch any miss as an unused-import error, but do not rely on the linter alone — fix it directly.
- **[Risk] The `rg` acceptance check scope (`src/ docs/ openspec/ tests/ README.md`) catches files outside the report's named list**: `docs/reference/tools/index.md`, `docs/_wip/v2.md`, `tests/ottools/unit/tools/test_forge.py`, `tests/explore/sanity.md` all contain matches today. → Mitigation: tasks.md includes all of them explicitly, not just the report's named subset.
- **[Risk] The delta-spec mechanism only patches `## Requirements` sections, not the `## Purpose` prose at the top of `serve-skills/spec.md` and `ottools/tool-forge/spec.md`.** After archive/sync, `serve-skills`'s Purpose line ("Defines the `ot.skills()` API...") and `tool-forge`'s Purpose line ("...and installing skill stubs for AI tools.") will still read as if the old API exists, even though every Requirement under them has changed. → Mitigation: tasks.md includes an explicit manual-edit task for both Purpose lines, to run after `openspec sync`/`archive`, since the tool will not do this automatically.
- **[Trade-off] No replacement skill installer ships in OneTool.** Users lose a one-command `ot_forge.install_skills()` and must run an external tool. This is accepted as the explicit point of the change (external installers own delivery) — do not treat the resulting UX gap as a bug to silently patch with a new internal installer.

## Migration Plan

1. Land `skills/ot-ref/SKILL.md` and `skills/ot-ref/agents/openai.yaml` first (additive, no removal yet) so the new location exists before the old one is deleted.
2. Delete the runtime-serving path, then the installer path, then the stale `global_templates` content — in that order, so each deletion's own tests can be removed/updated incrementally and `just check` stays green between steps if the implementer wants to checkpoint.
3. Update specs, then docs, then the `.codex/` working-tree cleanup (order doesn't matter for the last two, but do them after the code changes so doc text matches the final API surface, not an intermediate one).
4. No data migration, no config migration, no runtime rollback plan needed — this is a pure code/doc/spec removal with no persisted state.

## Open Questions

None — all decisions above were resolved by the maintainer ruling captured in `wip/release-v3/release-v3-report-2.md` R1 and the issue file; nothing here is deferred to the implementer's judgment.

## Implementation guardrails

- **No compatibility shims or aliases.** `ot.skills` and `ot_forge.install_skills` are removed, not deprecated-with-warning, not aliased to a no-op, not kept as a stub that raises `NotImplementedError`. If a call site still needs something equivalent, that is a signal the removal is incomplete — do not paper over it with a shim.
- **No stubbing or TODO-deferral.** If any task below cannot be completed as written (e.g. a file:line anchor has drifted further, a test asserts something not covered here), stop and report the discrepancy rather than commenting out the assertion, skipping the test, or leaving a `# TODO`.
- **Every code change gets a test update in the same task**, using this repo's markers (`@pytest.mark.unit`, `@pytest.mark.tools`, `@pytest.mark.serve` as appropriate — see the existing test files being edited for the marker convention already in use). `just check` (lint + typecheck + test) MUST pass before the change is considered complete.
- **Every `rg` command listed in tasks.md's Verification section that must return empty MUST actually be run, and MUST actually return empty** — not "should return empty" reasoning from reading the diff. If it doesn't, fix the remaining reference before marking the task done.
- **Do not draft new `ot-ref` content.** The verbatim-move task must produce byte-identical frontmatter and body to the current `src/ot/config/global_templates/skills/ot-ref.md` (modulo the file's new path). Any temptation to "improve" the description while moving it belongs to `p21-run-contract-and-command-index`, not here.
