# Tasks: Add ot.help()

## 1. Implementation

- [ ] 1.1 Add `DOC_SLUGS` mapping dict in `src/ot/meta.py`
- [ ] 1.2 Add `_get_doc_url()` helper function
- [ ] 1.3 Add `_fuzzy_match()` helper using `difflib.SequenceMatcher`
- [ ] 1.4 Add `_format_general_help()` helper
- [ ] 1.5 Add `_format_tool_help()` helper
- [ ] 1.6 Add `_format_pack_help()` helper
- [ ] 1.7 Add `_format_search_results()` helper
- [ ] 1.8 Implement `help()` function with routing logic
- [ ] 1.9 Register `help` in `get_ot_pack_functions()` dict

## 2. Testing

- [ ] 2.1 Add `tests/unit/test_meta_help.py`
- [ ] 2.2 Test general help output (no query)
- [ ] 2.3 Test exact tool lookup (`brave.search`)
- [ ] 2.4 Test exact pack lookup (`firecrawl`)
- [ ] 2.5 Test snippet lookup (`$b_q`)
- [ ] 2.6 Test alias lookup
- [ ] 2.7 Test fuzzy search with typos
- [ ] 2.8 Test info levels (`list`, `min`, `full`)
- [ ] 2.9 Test doc URL generation

## 3. Documentation

- [ ] 3.1 Update `docs/reference/tools/ot.md` with `ot.help()` section
