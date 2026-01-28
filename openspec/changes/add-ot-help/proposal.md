# Change: Add ot.help() unified help function

## Why

Users need a single entry point to get help on OneTool commands, tools, packs, snippets, and aliases. Currently, they must know to call `ot.tools()`, `ot.packs()`, `ot.snippets()`, or `ot.aliases()` separately. A unified `ot.help()` function provides:

- General overview when called with no arguments
- Specific help for any tool, pack, snippet, or alias by name
- Fuzzy search across all types for discovery

## What Changes

- Add `ot.help()` function to the `ot` pack
- Add `_fuzzy_match()` helper using stdlib `difflib.SequenceMatcher`
- Add `_get_doc_url()` helper for documentation URL generation
- Add formatting helpers for different output types

## Impact

- Affected specs: `tool-ot`
- Affected code: `src/ot/meta.py`
- No breaking changes - additive only

## Design Reference

Detailed design decisions documented in `plan/consult/ot-help-design.md`:
- Parameter naming (`query` not `q`)
- Fuzzy matching algorithm (stdlib, no new dependencies)
- Output format (markdown)
- Documentation URL mapping (hardcoded for 6 misaligned packs)
