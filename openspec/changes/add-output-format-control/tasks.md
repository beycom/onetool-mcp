# Tasks

## 1. Core Formatting

- [ ] 1.1 Add `format` parameter to `serialize_result()` in `src/ot/utils/format.py`
- [ ] 1.2 Implement `json_h` format (pretty JSON with 2-space indent)
- [ ] 1.3 Implement `yml` format (YAML flow style)
- [ ] 1.4 Implement `yml_h` format (YAML block style)
- [ ] 1.5 Implement `md` format with table support for list-of-dicts
- [ ] 1.6 Implement `raw` format (str() conversion)

## 2. Runner Integration

- [ ] 2.1 Read `__format__` from namespace in `execute_python_code()` in `src/ot/executor/runner.py`
- [ ] 2.2 Pass format to `serialize_result()` calls

## 3. Testing

- [ ] 3.1 Add unit tests for each format mode in `tests/unit/utils/test_format.py`
- [ ] 3.2 Add integration test for `__format__` magic variable
- [ ] 3.3 Test default behaviour unchanged (compact JSON)

## 4. Documentation

- [ ] 4.1 Update prompts.yaml run tool description to mention `__format__`
