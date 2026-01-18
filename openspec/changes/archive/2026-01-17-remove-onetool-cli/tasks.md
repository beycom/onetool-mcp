# Tasks: Remove onetool CLI

## 1. Remove onetool Package

- [x] 1.1 Delete `src/onetool/` directory
- [x] 1.2 Remove `onetool` entry point from `pyproject.toml`
- [x] 1.3 Remove `onetool` from `tool.hatch.build.targets.wheel.packages`
- [x] 1.4 Remove `src/onetool/*.py` from `tool.ruff.lint.per-file-ignores`

## 2. Remove onetool-cli Spec

- [x] 2.1 Delete `openspec/specs/onetool-cli/` directory

## 3. Update project.md

- [x] 3.1 Remove `onetool (config)` from CLIs list in `openspec/project.md`
- [x] 3.2 Remove `onetool upgrade` reference from Configuration section

## 4. Update Documentation

- [x] 4.1 Update `docs/getting-started/quickstart.md` - use `uv tool install`
- [x] 4.2 Update `docs/getting-started/installation.md` - new installation method
- [x] 4.3 Update `docs/reference/cli/index.md` - remove onetool section
- [x] 4.4 Update `README.md` - new installation instructions

## 5. Update Tool Docs (remove onetool references)

- [x] 5.1 Update `docs/reference/tools/diagram.md` - remove `onetool diagram` references

## 6. Additional Changes (discovered during implementation)

- [x] 6.1 Move `onetool.paths` to `ot.paths` (shared path utilities)
- [x] 6.2 Update all imports from `onetool.paths` to `ot.paths`
- [x] 6.3 Remove `tests/smoke/test_cli_onetool.py`

## 7. Validation

- [x] 7.1 Run `uv sync` to verify package still builds
- [x] 7.2 Run `uv run ot-serve --help` to verify server works
- [x] 7.3 Run tests: `uv run pytest tests/smoke -m "not network"` - 11 passed
- [x] 7.4 Verify `onetool` command no longer exists after reinstall
