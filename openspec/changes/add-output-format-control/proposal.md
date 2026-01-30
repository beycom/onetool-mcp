# Change: Add Output Format Control

## Why

Results from the `run` command are currently serialised as compact JSON (`{"key":"value"}`) which is hard to read in chat interfaces. Users need control over output formatting for better readability without changing the MCP interface or default behaviour.

## What Changes

- Add `__format__` magic variable support in executed code
- Support format modes: `json` (default compact), `json_h` (human-readable), `yml`, `yml_h`, `md`, `raw`
- Extend `serialize_result()` to accept an optional format parameter
- Read `__format__` from execution namespace after code runs

## Impact

- Affected specs: `serve-run-tool`
- Affected code: `src/ot/utils/format.py`, `src/ot/executor/runner.py`
- Backward compatible: default behaviour unchanged (compact JSON)
- New dependency: PyYAML (already in project for config loading)
