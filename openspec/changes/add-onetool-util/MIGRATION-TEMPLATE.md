# Migration Tracking: onetool-mcp → onetool-util

**Purpose:** Track all files copied from onetool-mcp to onetool-util.

**Usage:** This file will be used in **Proposal 4 (refactor-onetool-mcp)** to safely remove duplicated files from onetool-mcp.

**Status:** Template - will be populated during implementation (Phase 15)

---

## Code Files

### Tool Packs

**File pack:**
- [ ] `src/ot_tools/file.py` → `src/otutil/tools/file.py`

**Excel pack:**
- [ ] `src/ot_tools/excel.py` → `src/otutil/tools/excel.py`

**Convert pack:**
- [ ] `src/ot_tools/convert.py` → `src/otutil/tools/convert.py`
- [ ] `src/ot_tools/_convert/__init__.py` → `src/otutil/tools/_convert/__init__.py`
- [ ] `src/ot_tools/_convert/pdf.py` → `src/otutil/tools/_convert/pdf.py`
- [ ] `src/ot_tools/_convert/word.py` → `src/otutil/tools/_convert/word.py`
- [ ] `src/ot_tools/_convert/powerpoint.py` → `src/otutil/tools/_convert/powerpoint.py`
- [ ] `src/ot_tools/_convert/excel.py` → `src/otutil/tools/_convert/excel.py`
- [ ] `src/ot_tools/_convert/utils.py` → `src/otutil/tools/_convert/utils.py`

**Brave Search pack:**
- [ ] `src/ot_tools/brave_search.py` → `src/otutil/tools/brave.py` (renamed)

**Grounding Search pack:**
- [ ] `src/ot_tools/grounding_search.py` → `src/otutil/tools/ground.py` (renamed)

---

## Test Files

### Tool Tests

**File pack tests:**
- [ ] `tests/test_tools/test_file.py` → `tests/test_tools/test_file.py`
- [ ] Related fixtures in `tests/conftest.py` (sections to note)

**Excel pack tests:**
- [ ] `tests/test_tools/test_excel.py` → `tests/test_tools/test_excel.py`
- [ ] Related fixtures in `tests/conftest.py` (sections to note)

**Convert pack tests:**
- [ ] `tests/test_tools/test_convert.py` → `tests/test_tools/test_convert.py`
- [ ] Test data files: `tests/test_data/` (if any for convert)

**Brave Search tests:**
- [ ] `tests/test_tools/test_brave*.py` → `tests/test_tools/test_brave.py`
- [ ] Mock fixtures for Brave API

**Grounding Search tests:**
- [ ] `tests/test_tools/test_ground*.py` → `tests/test_tools/test_ground.py`
- [ ] Mock fixtures for Google Grounding API

---

## OpenSpec Files

### Tool Specifications

- [ ] `openspec/specs/tool-file/` → `openspec/specs/tool-file/`
  - [ ] `spec.md`
  - [ ] Any other spec files in directory

- [ ] `openspec/specs/tool-excel/` → `openspec/specs/tool-excel/`
  - [ ] `spec.md`
  - [ ] Any other spec files in directory

- [ ] `openspec/specs/tool-convert/` → `openspec/specs/tool-convert/`
  - [ ] `spec.md`
  - [ ] Any other spec files in directory

- [ ] `openspec/specs/tool-brave/` → `openspec/specs/tool-brave/`
  - [ ] `spec.md`
  - [ ] Any other spec files in directory

- [ ] `openspec/specs/tool-ground/` → `openspec/specs/tool-ground/`
  - [ ] `spec.md`
  - [ ] Any other spec files in directory

---

## Documentation

### README Sections

**Sections copied from onetool-mcp README.md:**
- [ ] Tool overview for file operations (line range: TBD)
- [ ] Tool overview for Excel manipulation (line range: TBD)
- [ ] Tool overview for document conversion (line range: TBD)
- [ ] Tool overview for Brave search (line range: TBD)
- [ ] Tool overview for Grounding search (line range: TBD)

### Tool Documentation

**From docs/ directory:**
- [ ] `docs/tools/file.md` → (if exists, note path)
- [ ] `docs/tools/excel.md` → (if exists, note path)
- [ ] `docs/tools/convert.md` → (if exists, note path)
- [ ] `docs/tools/brave.md` → (if exists, note path)
- [ ] `docs/tools/grounding.md` → (if exists, note path)

### Configuration Documentation

**Tool-specific config sections:**
- [ ] File pack config docs (from config guide)
- [ ] Excel pack config docs (from config guide)
- [ ] Convert pack config docs (from config guide)
- [ ] Brave API config docs (from config guide)
- [ ] Grounding API config docs (from config guide)

### Examples

**Example code/usage:**
- [ ] File operation examples
- [ ] Excel manipulation examples
- [ ] Document conversion examples
- [ ] Search examples (Brave and Grounding)

---

## Summary Statistics

**Total files copied:** TBD (to be counted in Phase 15)

**By category:**
- Code files: TBD
- Test files: TBD
- Spec directories: 5
- Doc files/sections: TBD

**Lines of code:** TBD (to be measured)

**Dependencies extracted:**
- openpyxl (Excel)
- pymupdf (PDF conversion)
- python-docx, python-pptx (Office conversion)
- google-genai (Grounding search)
- trafilatura (Web content extraction)

---

## Removal Checklist (For Proposal 4)

**When removing from onetool-mcp:**

1. [ ] Verify all files above exist in onetool-util
2. [ ] Run onetool-util tests - ensure all pass
3. [ ] Delete files from onetool-mcp (use this checklist)
4. [ ] Update onetool-mcp imports/dependencies
5. [ ] Update onetool-mcp to proxy to onetool-util backend
6. [ ] Run onetool-mcp tests in proxy mode
7. [ ] Verify no broken references

---

**Note:** This file will be created in onetool-util repo during Phase 15.
It serves as the authoritative record for Proposal 4's deletion tasks.
