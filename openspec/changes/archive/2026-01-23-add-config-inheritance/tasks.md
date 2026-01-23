## 1. Package Bundled Configs

- [x] 1.1 Create `src/ot/config/defaults/` directory
- [x] 1.2 Move YAML configs from `resources/config/` to `src/ot/config/defaults/`
  - `ot-serve.yaml`, `ot-bench.yaml`, `ot-browse.yaml`
  - `prompts.yaml`, `snippets.yaml`, `servers.yaml`, `diagram.yaml`
  - `secrets.yaml` (template)
- [x] 1.3 Move `resources/config/diagram-templates/` to `src/ot/config/defaults/diagram-templates/`
- [x] 1.4 Add `get_bundled_config_dir()` function to `src/ot/paths.py` using `importlib.resources`
- [x] 1.5 Update `ensure_global_dir()` to copy from bundled instead of filesystem path
- [x] 1.6 Add unit tests for `get_bundled_config_dir()` and updated `ensure_global_dir()`

## 2. CLI Bootstrap

- [x] 2.1 Add `ensure_global_dir(quiet=True)` call to `src/ot_serve/cli.py` main callback
- [x] 2.2 Add `ensure_global_dir(quiet=True)` call to `src/ot_bench/cli.py` main callback
- [x] 2.3 Add `ensure_global_dir(quiet=True)` call to `src/ot_browse/app.py` startup
- [x] 2.4 Verify bootstrap works with `rm -rf ~/.onetool && ot-serve --help`

## 3. Three-Tier Include Fallback

- [x] 3.1 Add `_resolve_include_path()` function to `src/ot/config/loader.py`
  - Search order: config_dir -> global -> bundled
  - Support absolute paths (use as-is)
  - Support ~ expansion
- [x] 3.2 Update `_load_includes()` to use new resolution function
- [x] 3.3 Add debug logging for resolved include paths
- [x] 3.4 Add unit tests for three-tier include resolution

## 4. Config Inheritance Directive

- [x] 4.1 Add `inherit` field to config models (values: `global`, `bundled`, `none`)
- [x] 4.2 Implement `_deep_merge()` helper function for dict merging
- [x] 4.3 Update `load_config()` to handle inheritance:
  - `inherit: global` (default) - merge global config first, project overrides
  - `inherit: bundled` - merge bundled defaults only
  - `inherit: none` - no merging
- [x] 4.4 Add unit tests for inheritance behaviour
- [x] 4.5 Add integration test: minimal project config with global inheritance

## 5. Documentation

- [x] 5.1 Update `docs/configuration.md` with three-tier resolution explanation
- [x] 5.2 Document `inherit` directive with examples
- [x] 5.3 Add migration notes (none required - backwards compatible)

## 6. Cleanup

- [x] 6.1 Remove `resources/config/` directory (now in src/ot/config/defaults/)
- [x] 6.2 Update any references to `resources/config/` in docs or comments
- [x] 6.3 Run full test suite to verify no regressions
