## Why

OneTool currently bundles skills (`ot-ref`) as an in-package resource served two ways: a runtime MCP tool (`ot.skills()`) that returns skill Markdown on demand, and an installer tool (`ot_forge.install_skills()`) that renders per-agent stub files into `.claude/`, `.codex/`, `.opencode/`, `.pi/`. Both mechanisms predate the now-standard Agent Skills layout (`skills/<name>/SKILL.md` at the repo root, discoverable by external installers such as `npx skills add`). Per maintainer ruling (2026-07-03), both the runtime serving path and the installer path are deprecated-for-removal in V3 (a breaking window: removed cleanly, no shim, no alias) — external installers now own delivery, and OneTool should ship the skill as a standard top-level file, not as a served/installed resource.

The current spec (`openspec/specs/serve-skills/spec.md`) also requires three bundled skills (`ot-ref`, `ot-chrome-devtools-mcp`, `ot-playwright-mcp`), but only `ot-ref` exists — the other two are referenced in the spec and in `docs/reference/tools/ot_core.md:324` and `src/ottools/skills.py:8` but were never built. This change also resolves that spec/reality drift.

## What Changes

- Create `skills/ot-ref/SKILL.md` (top-level, standard Agent Skills layout) as the **only** copy of the `ot-ref` skill — a verbatim move of the current content at `src/ot/config/global_templates/skills/ot-ref.md` (frontmatter + body unchanged; content **rewrite** — new description/trigger/body — is explicitly out of scope for this change, see Impact).
- Create `skills/ot-ref/agents/openai.yaml` — a net-new Codex sidecar (OpenAI Codex Skills `agents/openai.yaml` format) with `policy.allow_implicit_invocation: true`. **Rejected alternative**: the source issue (`wip/release-v3/issues/move-skills-to-standard-repo-layout.md`) proposed `allow_implicit_invocation: false` to keep `ot-ref` an explicit/reference-only skill. The maintainer explicitly overruled this: `ot-ref` is a proactive tools-leverage skill (covers the runtime's underexplored forgiveness — param prefixes, aliases, recovery seams) and should be allowed to trigger implicitly. Do not implement the issue's `false` value.
- **BREAKING**: Remove the `ot.skills()` MCP tool entirely (no shim, no alias). Delete `src/ottools/skills.py` (whole module — confirmed dead code, see Design), the `ot.skills` wiring in `src/ot/meta/__init__.py` (import at line 42, `__all__` entry at line 81, dict entry at line 120), the `skills()` wrapper function in `src/ot/meta/_server_mgmt.py` (lines 78–102), and `src/ot/meta/_skills_services.py` (whole module — the actual live implementation `ot.skills()` delegated to).
- **BREAKING**: Remove the `ot_forge.install_skills()` MCP tool entirely (no shim, no alias). Delete `install_skills()` and its four private helpers (`_get_tools_config`, `_get_skill_stub_template`, `_list_bundled_skills`, `_get_skill_description`, `_get_skill_body`) from `src/ottools/ot_forge.py` (lines 367–540), plus `src/ot/config/global_templates/skills.md` (per-agent stub path config) and `src/ot/config/global_templates/skill_stub.md.j2` (Jinja2 stub template).
- Delete `src/ot/config/global_templates/skills/ot-ref.md` (superseded by the top-level `skills/ot-ref/SKILL.md`).
- Remove the `ot.skills(name='ot-ref')` instructions pointer from `src/ot/config/global_templates/prompts.yaml:41` — agents now get the advanced reference through their host's installed skill (the standard's whole point), not through a server-side pointer.
- Replace `openspec/specs/serve-skills/spec.md` entirely: remove the runtime-API requirements (Skills Listing, Skill Content Retrieval, Bundled Skill Set), add requirements describing the new distribution contract (top-level `skills/` layout, frontmatter contract, Codex sidecar, external-installer discovery, no server-side serving).
- Amend `openspec/specs/serve-run-tool/spec.md` and `openspec/specs/serve-prompts/spec.md` to remove their `ot.skills` references.
- Amend `openspec/specs/ottools/tool-forge/spec.md` to remove the `install_skills()`-related requirements (Install Skill Stub Function, Stub File Format, Tool Path Configuration).
- Update docs (`docs/reference/tools/ot_core.md`, `docs/reference/tools/ot_forge.md`, `docs/reference/tools/tool-index.md`, `docs/reference/tools/index.md`, `docs/learn/whats-new-v2.md`, `docs/learn/installation.md`, `docs/_wip/v2.md`) and `README.md` to drop all `ot.skills`/`install_skills` references and add an "install the OneTool skills" step recommending `npx skills add <repo> --skill ot-ref --agent <agent>` (vercel-labs/skills) as the primary install path, with APM or manual copy mentioned as alternatives. Fix the non-existent `ot-chrome-devtools-mcp` demo references.
- Remove/update tests: delete `tests/ottools/unit/tools/test_skills.py` and `tests/ottools/unit/tools/test_forge_skills.py`; update `tests/unit/serve/test_slim_prompt.py` (drop the `ot.skills` assertion), `tests/ottools/unit/tools/test_forge.py` (drop `install_skills` from the expected `__all__` set), `tests/explore/sanity.md` (drop `install_skills` from the `ot_forge` smoke-test list). `tests/unit/core/test_paths.py` needs no edits — verified its assertions already assert the *absence* of `skills.md`/`skills/` from the copied `.onetool/` dir (they are not in `INIT_TEMPLATE_FILES`/`INIT_TEMPLATE_DIRS`), so they remain true after this deletion; re-run them to confirm no drift.
- Clean up the local working-tree artifact `.codex/skills/ot-ref/SKILL.md` (gitignored via `.codex/`, not tracked, but a stale/drifted copy that should not linger during this change).

## Capabilities

### New Capabilities

(none — the `skills/` top-level layout is a distribution/file-layout change with no new runtime tool contract; its verifiable outcomes are folded into the `serve-skills` capability delta below, per the "docs-only changes still get a spec" rule.)

### Modified Capabilities

- `serve-skills`: full replacement — remove the `ot.skills()` runtime API requirements, add the standard top-level `skills/` distribution contract requirements (file layout, frontmatter, Codex sidecar, external-installer discovery, explicit no-server-side-serving statement).
- `serve-run-tool`: the "Robust Result Capture" requirement's "Discovery calls keep JSON default format" scenario currently lists `ot.skills` among discovery/introspection tools; remove it from the list (tool no longer exists).
- `serve-prompts`: the "Server Instructions" requirement ("Instructions are concise", "Discovery hint present" scenarios) and the "Tool-Specific Prompts" requirement ("Run description includes proxy + reference guidance" scenario) reference `ot.skills(name="ot-ref")` as an optional pointer; remove all three references (deleted, not replaced — see prompts.yaml:41 change above).
- `ottools/tool-forge`: remove the "Install Skill Stub Function", "Stub File Format", and "Tool Path Configuration" requirements (the `install_skills()` API surface).

## Impact

- Affected code: `src/ottools/skills.py` (deleted), `src/ottools/ot_forge.py` (~175 lines removed), `src/ot/meta/__init__.py`, `src/ot/meta/_server_mgmt.py`, `src/ot/meta/_skills_services.py` (deleted), `src/ot/config/global_templates/{skills/,skills.md,skill_stub.md.j2,prompts.yaml}`.
- Affected specs: `serve-skills` (replaced), `serve-run-tool`, `serve-prompts`, `ottools/tool-forge` (amended).
- Affected docs: `docs/reference/tools/{ot_core.md,ot_forge.md,tool-index.md,index.md}`, `docs/learn/{whats-new-v2.md,installation.md}`, `docs/_wip/v2.md`, `README.md`.
- Affected tests: `tests/ottools/unit/tools/{test_skills.py (deleted),test_forge_skills.py (deleted),test_forge.py}`, `tests/unit/serve/test_slim_prompt.py`, `tests/explore/sanity.md`.
- Tool surface: removes two MCP-visible functions (`ot.skills`, `ot_forge.install_skills`) from the runtime registry; `ot` pack tool count drops by 1, `ot_forge` pack tool count drops by 1.
- **Dependency**: `p21-run-contract-and-command-index` depends on this change. This change moves the `ot-ref` content verbatim and creates the distribution scaffold only; the actual content **rewrite** of `skills/ot-ref/SKILL.md` (new proactive-trigger description, the pack surface, param-prefix/alias forgiveness, and the greppable command index) is owned by p21 and must land after this change merges. Do not draft new skill prose here.
- No runtime behavior change for existing `pack.tool(...)` calls — this is a distribution/tool-surface change only.
