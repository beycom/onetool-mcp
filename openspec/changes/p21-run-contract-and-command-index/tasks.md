# Tasks: p21-run-contract-and-command-index

Prerequisite: `p11-skills-standard-layout` is implemented (the `skills/ot-ref/` layout exists and
`ot.skills`/`install_skills` are gone). Do not start before that.

The file contents in `design.md` §A–§D are EXACT deliverables — copy them verbatim; do not
paraphrase or reformat. If a genuine defect is found (YAML/schema error, wrong signature), apply
the minimal correction and record it in the task notes.

## 1. prompts.yaml rewrite (design §A)

- [x] 1.1 Replace `src/ot/config/global_templates/prompts.yaml` with the exact content in design §A
- [x] 1.2 Update prompt-content unit tests to assert the new content (new examples list, single
      colon-rule statement, two-request-forms block, skill pointer, `localhist` pack entry, no
      `ot.skills` reference) — locate via `rg -ln "brave.search|ot.skills" tests/`
- [ ] 1.3 Fresh-install smoke: on a base install with no secrets, execute each of the four
      examples via `run` and confirm success; if `ripgrep.search` fails for a missing `rg`
      binary, substitute `file.read(path='README.md')` per design §A note and update tests

## 2. ot.tools(info='signatures') (design §G)

- [x] 2.1 Extract `signature_args`/`short_description` helpers to a core-visible module (e.g.
      `src/ot/meta/_signatures.py`); make `src/otdev/docsgen/tool_index.py` import them from
      there (`ot` core MUST NOT import `otdev.*`)
- [x] 2.2 Add `"signatures"` to `InfoLevel` (`src/ot/meta/_constants.py`) and
      `_VALID_INFO_LEVELS` (`src/ot/meta/_discovery.py:20`); implement the level in `tools()`
      returning `pack.tool(compact_args)  # first-line description` one-liners; update the
      docstring and examples
- [x] 2.3 Unit tests: signatures level returns the one-liner format; single-pack pattern returns
      only that pack; invalid info value error names `signatures`; rendering matches the
      tool-index file format for a sampled tool

## 3. Skill content (design §B–§D)

- [x] 3.1 Replace `skills/ot-ref/SKILL.md` with the exact content in design §B
- [x] 3.2 Write `skills/ot-ref/agents/openai.yaml` with the exact content in design §C
      (implicit invocation MUST remain allowed — never `false`)
- [x] 3.3 Write `skills/ot-ref/reference/recovery.md` with the exact content in design §D
- [x] 3.4 Delete any leftover old ot-ref body content (the "ot-ref is optional" opener MUST NOT
      survive anywhere): `rg -n "ot-ref is optional" .` returns nothing

## 4. Generators (design §E–§F)

- [x] 4.1 Extend `src/otdev/docsgen/tool_index.py` `main()` to also write
      `skills/ot-ref/reference/tool-index.md` (byte-identical to the docs copy); wire into the
      same sync path as `scripts/sync_docs_generated.py`
- [x] 4.2 Add a staleness check (in `scripts/check_docs_registry.py` or the generated-blocks
      check) failing when the skill copy differs from a fresh generation; regenerate and commit
      the current index
- [x] 4.3 New `src/otdev/docsgen/skill_pack_map.py` (logic ported from
      `_build_pack_summary()`, `src/ot/server.py:208-238`, extended with registry aliases)
      rewriting the `<!-- packmap:begin -->`…`<!-- packmap:end -->` block in SKILL.md, following
      the `generated_blocks.py` marker pattern; run it and commit the generated map
- [x] 4.4 Delete `_build_pack_summary()` and the `{pack_summary}` branch in `_get_instructions()`
      from `src/ot/server.py`; update/remove their tests
- [x] 4.5 Unit tests: docsgen emits both index copies identical; pack-map generator includes
      aliases (`whiteboard` shows `wb`); marker block round-trips idempotently

## 5. Verification

- [x] 5.1 `rg -n "pack_summary" src/ot/` returns nothing
- [x] 5.2 `rg -n "ot\.skills" src/ docs/ README.md tests/` returns nothing (p11 owns the bulk;
      confirm this change reintroduced none)
- [x] 5.3 `rg -n "brave.search" src/ot/config/global_templates/prompts.yaml` returns nothing
      (no key-gated example)
- [x] 5.4 The colon rule appears exactly once in prompts.yaml (`rg -c "colon|snippets only"` —
      inspect manually; one statement with the right/wrong pair)
- [x] 5.5 `diff docs/reference/tools/tool-index.md skills/ot-ref/reference/tool-index.md`
      is empty after a fresh generation run
- [x] 5.6 `uv run python scripts/check_docs_registry.py` passes
- [x] 5.7 `just check` passes
- [ ] 5.8 Manual harness check: in a Claude Code or Codex session with the skill installed, a
      OneTool task loads ot-ref BEFORE the first pack call (record the observation in the task
      notes; this validates the trigger posture)
