# Change: Switch Tool Output Format from YAML to JSON

## Why

LLMs are trained extensively on JSON and use it natively for function calling and tool use. YAML flow style, while compact, introduces parsing ambiguity (Norway problem, yes/no booleans) and requires custom quoters for special characters. Switching to JSON aligns tool output with the MCP protocol format and improves LLM parsing reliability.

## What Changes

- Modify `tool-conventions` spec to require JSON instead of YAML for structured data output
- Add centralised `format_result()` helper in `src/ot/utils/format.py`
- Update all tool modules to use JSON output:
  - `excel.py` (13 locations)
  - `package.py` (1 location)
  - `file.py` (1 location)
  - `internal.py` (2 locations)
  - `registry.py` (1 location - LLM context)
- Remove custom YAML dumper classes (`FlowDumper`, `_BlockStyleDumper`)

## Out of Scope

- Configuration files remain YAML (human-edited, benefit from comments)
- Benchmark spec files remain YAML (human-edited)
- Browse storage remains YAML (multiline block style for page content)
- Bench results output file (optional future change)

## Impact

- Affected specs: `tool-conventions`
- Affected code: `src/ot_tools/excel.py`, `src/ot_tools/package.py`, `src/ot_tools/file.py`, `src/ot_tools/internal.py`, `src/ot/registry/registry.py`
- New file: `src/ot/utils/format.py`
- Tests requiring update: Tool output assertions in `tests/unit/tools/`
