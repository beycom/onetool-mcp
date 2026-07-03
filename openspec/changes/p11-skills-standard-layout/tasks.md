## 1. Create the standard-layout skill distribution

- [ ] 1.1 Create directory `skills/ot-ref/agents/` at the repository root (net new top-level `skills/` dir).
- [ ] 1.2 Move `src/ot/config/global_templates/skills/ot-ref.md` to `skills/ot-ref/SKILL.md` byte-for-byte (use `git mv` so it's tracked as a rename, not a delete+recreate — this guarantees the frontmatter and body are not accidentally retyped). Do **not** edit the frontmatter (`name`, `description`, `tags`) or body content as part of this move — the content is:
  ```yaml
  ---
  name: ot-ref
  description: OneTool __onetool/MCP run reference for direct pack calls, recovery, proxy handling, ctx handles, and run-vs-local-script decisions
  tags: [reference, cheatsheet]
  ---
  ```
  followed by the existing body (Fast Recovery, Proxy Server Recovery, Security Boundaries, Decision Boundary, Output Controls, ctx Handle Trap sections). Content **rewrite** is out of scope — owned by `p21-run-contract-and-command-index` (see proposal.md Impact).
- [ ] 1.3 Create `skills/ot-ref/agents/openai.yaml` (net new — no `openai.yaml` exists anywhere in the repo today) with:
  ```yaml
  policy:
    allow_implicit_invocation: true
  ```
  Do not set this to `false`. The source issue (`wip/release-v3/issues/move-skills-to-standard-repo-layout.md`) proposed `false`; the maintainer explicitly overruled it — `ot-ref` is a proactive tools-leverage skill and should trigger implicitly. See design.md "Decisions" for the full rationale; do not second-guess this value.
- [ ] 1.4 Delete the now-empty `src/ot/config/global_templates/skills/` directory, including `src/ot/config/global_templates/skills/__init__.py` (0 bytes, packaging marker only — confirmed no other files live in this directory).

## 2. Delete the runtime-serving path (`ot.skills`)

- [ ] 2.1 Delete `src/ottools/skills.py` in full (confirmed dead code — no `pack = "..."` module attribute, structurally unreachable via `build_execution_namespace()` in `src/ot/executor/pack_proxy.py`; exercised only by its own test file, removed in task 7.1).
- [ ] 2.2 Delete `src/ot/meta/_skills_services.py` in full (this is the actual live implementation `ot.skills()` currently delegates to).
- [ ] 2.3 In `src/ot/meta/_server_mgmt.py`, delete the `skills()` function (currently lines 78-102, the last thing in the file — deleting it leaves the file ending at `server()`, line 76). Do **not** delete `security()` or `server()` in this same file — they back the live `ot.security`/`ot.server` tools and are out of scope.
- [ ] 2.4 In `src/ot/meta/__init__.py`, remove the `ot.skills` wiring in three places:
  - Line 42: change `from ot.meta._server_mgmt import security, server, skills` to `from ot.meta._server_mgmt import security, server` (drop `skills`).
  - Line 81: remove the `"skills",` entry from the `__all__` list.
  - Line 120: remove the `"skills": skills,` entry from `get_ot_pack_functions()`'s returned dict.
- [ ] 2.5 In `src/ot/config/global_templates/prompts.yaml`, delete line 41 entirely: `    Optional advanced reference: \`ot.skills(name='ot-ref')\` for recovery, proxy handling, ctx handles, output controls, and run-vs-local-script decisions.` Do not replace it with alternate wording — agents now get the advanced reference through their host's installed skill (this is the point of the standard layout). Leave the surrounding `instructions:` block otherwise unchanged (still ≤ 50 lines after the deletion, per `serve-prompts`'s "Instructions are concise" scenario).
- [ ] 2.6 In `src/ot/meta/_config_health.py`, update the stale doc comments in `reload()` that reference the removed skills index: line 178 (`    - Skills index (bundled skill content)` — remove this bullet from the docstring list) and line 216 (`_ot_cache.clear()  # Clears skills index and other TTL-cached data` — change the comment to `_ot_cache.clear()  # Clears TTL-cached data`). This is a comment-only cleanup; `reload()`'s actual behavior (`_ot_cache.clear()`) does not change.

## 3. Delete the installer path (`ot_forge.install_skills`)

- [ ] 3.1 In `src/ottools/ot_forge.py`, delete lines 367-540 in full: the `# Skill Installation` section header/comment block, `_get_tools_config()`, `_get_skill_stub_template()`, `_list_bundled_skills()`, `_get_skill_description()`, `_get_skill_body()`, and `install_skills()` (this is everything from the section header to end of file).
- [ ] 3.2 In the same file, update imports now that the deleted section was their only use site (verify with a grep for each name before removing — do not remove a name still used elsewhere):
  - Line 12: change `from typing import Any, cast` — remove entirely (both `Any` and `cast` are used only at the now-deleted lines 373/383).
  - Line 15: change `from otpack import LogSpan, cache, get_effective_cwd` to `from otpack import LogSpan` (`cache` was only used by the five `@cache.memoize` decorators in the deleted section; `get_effective_cwd` was only used at the deleted line 514; `LogSpan` remains used by `create_ext()`/`validate_ext()`).
  - Line 17: update the module comment `# Pack for dot notation: ot_forge.create_ext(), ot_forge.validate_ext(), ot_forge.install_skills()` to drop `, ot_forge.install_skills()`.
  - Line 21: change `__all__ = ["create_ext", "install_skills", "validate_ext"]` to `__all__ = ["create_ext", "validate_ext"]`.
- [ ] 3.3 Delete `src/ot/config/global_templates/skills.md` (per-agent stub path config, read only by the now-deleted `_get_tools_config()`).
- [ ] 3.4 Delete `src/ot/config/global_templates/skill_stub.md.j2` (Jinja2 stub template, read only by the now-deleted `_get_skill_stub_template()`).

## 4. Clean up working-tree artifacts

- [ ] 4.1 Delete `.codex/skills/ot-ref/SKILL.md` (a stray installed-artifact copy; `.codex/` is gitignored via `.gitignore:122` so this is a local cleanup only, not a git operation — confirm with `git status` that nothing under `.codex/` shows as a tracked change before/after).

## 5. Update documentation

- [ ] 5.1 `docs/reference/tools/ot_core.md`:
  - Line 30: remove the `| \`ot.skills(name, pattern, info)\` | List bundled skills or retrieve a skill body |` row from the functions table.
  - Line 57: remove `skills` from the `info` parameter's list of supporting discovery functions (`help, tools, tool_info, packs, pack_info, aliases, snippets, snippet_info, skills`).
  - Lines 303-328: delete the entire `## ot.skills()` section (heading through the closing `Skills are bundled \`.md\` files...` paragraph, including the non-existent `ot.skills(name="ot-chrome-devtools-mcp")` example at line 324).
- [ ] 5.2 `docs/reference/tools/ot_forge.md`:
  - Line 3: change `Create, validate, and install extension tools and skill stubs.` to `Create and validate extension tools.`
  - Line 12: remove the `- Skill stub installation for Claude, Codex, and OpenCode` highlight bullet.
  - Line 20: remove the `| \`ot_forge.install_skills(install, ...)\` | Install a skill stub for an AI tool |` row from the functions table.
  - Lines 41-47: delete the entire `### install_skills` parameters subsection.
  - Lines 85-98: delete the skill-listing/install example block (`# List available skills...` through `ot_forge.install_skills(exclude=["ot-ref"])`), leaving the `create_ext`/`validate_ext` examples above it intact.
- [ ] 5.3 `docs/reference/tools/index.md`:
  - Header line (`**27 Packs. 243 Tools.**` or current values): do not hand-guess the new total — this is derived in task 5.4 via the doc-sync scripts; update it to match whatever `scripts/check_docs_registry.py` reports as the runtime total after tasks 2-3 are complete.
  - OT Core row: remove `skills` from the trailing tool-name list and decrement the tool count column by 1.
  - OT Forge row: remove `install_skills` from the trailing tool-name list, decrement the tool count column by 1, and change the description cell from `Create, validate, and install extension tools and skill stubs.` to `Create and validate extension tools.`
- [ ] 5.4 Run `just docs-sync` (chains `scripts/sync_docs_generated.py`, `scripts/list_tool_inventory.py --tool-descriptions`, `scripts/check_docs_registry.py`) to regenerate `docs/reference/tools/tool-index.md` (currently has stale `ot.skills(...)` at line 210 and `ot_forge.install_skills(...)` at line 240 — both will disappear once the runtime registry no longer has these tools) and to validate the counts hand-edited in task 5.3 against the runtime registry. Fix any mismatch the script reports rather than silencing it.
- [ ] 5.5 `docs/learn/whats-new-v2.md`:
  - Lines 49-55 (`### skills — Bundled skill guides` section): rewrite to stop presenting `ot.skills()` as the live API — either remove the code example (`__onetool skills.skills()` / `__onetool skills.skills(name="ot-ref")`) or rephrase the section to describe the historical v2 behavior in past tense without implying the call still works today. Do not delete the whole section (it documents what changed in v2 for historical record) — just remove the now-false "this still works" implication.
  - Line 360 (`### User-defined skills removed` section body): change `Built-in skills like \`ot-ref\` are bundled and retrieved via \`ot.skills()\`.` to reflect the new distribution (e.g. "Built-in skills like `ot-ref` are distributed at `skills/ot-ref/SKILL.md` for installation via external skill tooling.").
- [ ] 5.6 `docs/_wip/v2.md` (historical v2.0.0→v2.1.0 release-notes source; not named in the source report but caught by the acceptance `rg` check below — must be cleaned for the gate to pass):
  - Line 37: change `- **Bundled skills** — curated guides for AWS, Chrome DevTools, Playwright via \`ot.skills()\`` to drop the `via \`ot.skills()\`` clause (keep the historical bullet, remove the now-dead API reference).
  - Line 44: change `- **User-defined skills removed** — use bundled skills via \`ot.skills()\` instead` similarly (drop the `via \`ot.skills()\`` clause).
- [ ] 5.7 `docs/learn/installation.md`: add a new step recommending the external skill installer, e.g. a `## Install the OneTool Skills` section (placed after `## MCP Configuration`, before `## External Tools`) containing:
  ```bash
  npx skills add https://github.com/beycom/onetool-mcp --skill ot-ref --agent claude
  ```
  with a short note that `--agent` accepts `codex`, `opencode`, etc., that `--list` discovers all installable skills, and that APM or manual copy of `skills/ot-ref/SKILL.md` are supported alternatives if not using vercel-labs/skills. Do not touch this file's existing "Python 3.11+" text or extras table — that drift is owned by `p18-docs-debt-sweep`.
- [ ] 5.8 `README.md`:
  - Line 147: change `| \`ot_forge\`    | \`create_ext\`, \`validate_ext\`, \`install_skills\` |          | Scaffold new tool packs        |` to drop `install_skills` from the tools cell.
  - Line 153: change `| \`ot\`          | \`help\`, \`tools\`, \`stats\`, \`skills\`             |          | Introspection                  |` to drop `skills` from the tools cell.
  - In the `## Install` section (after the existing `Verify:` line, before the `[📖 Full installation guide]` link), add a short step recommending `npx skills add <repo> --skill ot-ref --agent <agent>` (vercel-labs/skills) to install the `ot-ref` skill, consistent with task 5.7.

## 6. Update specs (delta files already written in this change — verify only)

- [ ] 6.1 Confirm `specs/serve-skills/spec.md`, `specs/serve-run-tool/spec.md`, `specs/serve-prompts/spec.md`, and `specs/ottools/tool-forge/spec.md` in this change directory parse correctly: run `openspec validate --change p11-skills-standard-layout` (or `openspec status --change p11-skills-standard-layout`) and confirm no scenario-header or delta-format errors.
- [ ] 6.2 After this change is archived/synced into the main specs (a separate step from `tasks.md` — see design.md "Migration Plan"), manually verify the `## Purpose` prose at the top of `openspec/specs/serve-skills/spec.md` and `openspec/specs/ottools/tool-forge/spec.md` no longer describes the removed `ot.skills()`/`install_skills()` APIs — the delta mechanism only patches `## Requirements` blocks, not `## Purpose`, so this needs a manual touch-up at archive time (see design.md "Risks").

## 7. Update tests

- [ ] 7.1 Delete `tests/ottools/unit/tools/test_skills.py` in full (tests the deleted `src/ottools/skills.py`).
- [ ] 7.2 Delete `tests/ottools/unit/tools/test_forge_skills.py` in full (tests the deleted `ot_forge.install_skills()`).
- [ ] 7.3 In `tests/ottools/unit/tools/test_forge.py`, line 49: change `expected = {"create_ext", "install_skills", "validate_ext"}` to `expected = {"create_ext", "validate_ext"}` (matches the `__all__` change in task 3.2).
- [ ] 7.4 In `tests/unit/serve/test_slim_prompt.py`:
  - Line 28: remove the assertion `assert "ot.skills(name='ot-ref')" in text, "Missing optional ot-ref pointer"` from `test_instructions_has_required_elements` (the pointer is deleted in task 2.5; do not replace it with an assertion for a different string unless you also add matching content — this task's scope is deletion, not rewriting the instructions prompt further, which is p21's job).
  - `test_ot_ref_contains_advanced_recovery_not_core_contract` (currently lines 111-122) reads the skill file to assert its content still carries advanced-recovery guidance and not the core invocation contract. Line 113's `from ot.paths import get_global_templates_dir` and line 115's `text = (get_global_templates_dir() / "skills" / "ot-ref.md").read_text()` both target the now-deleted `global_templates/skills/` location (drift not listed in the source report — found during spec-writing verification). Update it to read the moved file instead:
    ```python
    from pathlib import Path

    text = (Path(__file__).resolve().parents[3] / "skills" / "ot-ref" / "SKILL.md").read_text()
    ```
    (drop the now-unused `from ot.paths import get_global_templates_dir` import from this test if it is not used elsewhere in the file — verify with a grep before removing). Keep all five `assert` lines below (117-122) unchanged; the moved content is identical, so they still hold.
- [ ] 7.5 `tests/unit/core/test_paths.py`: no code changes required. Verify (do not skip) that lines 162 (`assert not (ot_dir / "skills.md").exists()`) and 176 (`assert not (ot_dir / "skills").exists()`) still pass after tasks 1-3 — they assert absence from `INIT_TEMPLATE_FILES`/`INIT_TEMPLATE_DIRS` (`src/ot/paths.py:32-45`), which never included `skills.md`/`skills/`, so these assertions were already true and remain true. Run the test file to confirm; do not edit it unless the run surfaces an actual failure.
- [ ] 7.6 `tests/explore/sanity.md`, line 33: change `- ot_forge: create_ext, validate_ext, install_skills` to `- ot_forge: create_ext, validate_ext` (this is a manual exploratory-test script, not a pytest file — no test runner change needed, just keep it accurate).

## Verification

- [ ] 8.1 Run `rg -n "install_skills|skill_stub|ot\.skills|ottools.skills" src/ docs/ openspec/ tests/ README.md` and confirm it returns **nothing** except matches inside the new `skills/` directory content itself (there should be none there either, since `skills/ot-ref/SKILL.md` and `agents/openai.yaml` don't reference any of these strings — if the command returns any match at all, treat it as a failure and fix it).
- [ ] 8.2 Run `rg -n "ot-chrome-devtools-mcp|ot-playwright-mcp"` (repo-wide) and confirm it returns **nothing**.
- [ ] 8.3 Confirm `skills/ot-ref/SKILL.md` exists at the repo root and `skills/ot-ref/agents/openai.yaml` exists, with the exact frontmatter/policy content specified in tasks 1.2-1.3.
- [ ] 8.4 If `npx` and network access are available in the implementation environment, run `npx skills add . --list` (or the equivalent pointed at this repo) from the repo root and confirm `ot-ref` is listed as discoverable. If `npx`/network access is not available in this environment, note that explicitly in the completion report rather than silently skipping — do not claim this check passed without running it.
- [ ] 8.5 Run `just lint` and `just typecheck` — confirm no unused-import errors in `src/ottools/ot_forge.py` (task 3.2) and no import errors in `src/ot/meta/__init__.py` (task 2.4).
- [ ] 8.6 Run `uv run pytest -m "unit and tools"` and `uv run pytest tests/unit/serve/test_slim_prompt.py tests/unit/core/test_paths.py` — confirm all pass with the deleted/updated tests from section 7.
- [ ] 8.7 Run `just check` (lint + typecheck + test) in full and confirm it passes.
- [ ] 8.8 Run `uv run python scripts/check_docs_registry.py` directly (already covered by `just docs-sync` in task 5.4, but re-run standalone here as the final gate) and confirm it prints `docs registry check passed`.
