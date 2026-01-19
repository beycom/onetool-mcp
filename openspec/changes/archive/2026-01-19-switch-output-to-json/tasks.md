# Tasks: Switch Tool Output Format from YAML to JSON

## 1. Core Infrastructure

- [x] 1.1 Create `src/ot/utils/format.py` with `format_result()` helper
- [x] 1.2 Add `format_result()` function with compact/pretty modes
- [x] 1.3 Export from `src/ot/utils/__init__.py`

## 2. Tool Migration

- [x] 2.1 Update `package.py` - replace `_to_yaml()` with `format_result()`
- [x] 2.2 Update `file.py` - replace `_format_yaml()` with `format_result()`
- [x] 2.3 Update `excel.py` - replace 13 `yaml.dump()` calls with `format_result()`
- [x] 2.4 Update `internal.py` - replace `_to_yaml_flow()` with `format_result()`, remove `FlowDumper`
- [x] 2.5 Update `registry.py` - replace `format_yaml()` with `format_json()`

## 3. Cleanup

- [x] 3.1 Remove `_to_yaml()` helper from `package.py`
- [x] 3.2 Remove `_format_yaml()` helper from `file.py`
- [x] 3.3 Remove `_to_yaml_flow()` and `FlowDumper` from `internal.py`
- [x] 3.4 Remove unused `import yaml` statements from tool files

## 4. Testing

- [x] 4.1 Update tool output assertions to expect JSON format
- [x] 4.2 Add unit tests for `format_result()` helper
- [x] 4.3 Run full test suite to verify no regressions

## 5. Documentation

- [x] 5.1 Update `docs/ot-tools.md` if it references YAML output format
