## Context

OneTool uses YAML configuration files for all three CLIs (ot-serve, ot-bench, ot-browse). The current design has a two-tier resolution: project `.onetool/` then global `~/.onetool/`. However:

1. Default configs in `resources/config/` are not included in the wheel package
2. `ensure_global_dir()` uses filesystem path traversal that fails when installed as a package
3. Include resolution is config-local only - no fallback to global or bundled defaults

This blocks the common use case of minimal project configs that inherit shared settings.

## Goals / Non-Goals

**Goals:**
- Package default configs so they're accessible after `uv tool install`
- Bootstrap `~/.onetool/` on first CLI run with sensible defaults
- Enable include fallback: project -> global -> bundled
- Add explicit `inherit` directive for config merging control
- Zero breaking changes for existing users

**Non-Goals:**
- Config migration tooling (not needed - backwards compatible)
- Merging of list fields (lists are replaced, not merged)
- Remote config fetching

## Decisions

### Decision 1: Use `src/ot/config/defaults/` for bundled configs

**What**: Move `resources/config/` contents to `src/ot/config/defaults/`.

**Why**: Python's `importlib.resources` provides reliable access to package data when installed. The `src/` layout means `src/ot/config/defaults/` is automatically included in the wheel without modifying `pyproject.toml`.

**Alternatives considered**:
- `package_data` in pyproject.toml - Requires explicit configuration, easy to misconfigure
- `data_files` - Platform-specific install locations, hard to locate at runtime
- Embed configs as Python strings - Poor maintainability, harder to edit

### Decision 2: Three-Tier Resolution Order

**What**: Include resolution searches: config_dir -> global -> bundled.

**Why**: Enables minimal project configs that only override what's different. Users can customise global once and have it apply everywhere.

```
+------------------+     +------------------+     +------------------+
|    Bundled       | --> |     Global       | --> |    Project       |
| (package data)   |     |  (~/.onetool/)   |     | (cwd/.onetool/)  |
+------------------+     +------------------+     +------------------+
   Read-only              User preferences        Project overrides
   Ship with pkg          API keys, prefs         tools_dir, etc.
```

### Decision 3: Implicit `inherit: global` Default

**What**: If `inherit` is not specified, configs implicitly merge with global.

**Why**: This matches user expectations - a minimal project config should "just work" with existing global settings. Users who want isolated configs can opt out with `inherit: none`.

### Decision 4: Deep Merge for Dicts, Replace for Lists

**What**: Nested dicts are recursively merged; lists are replaced entirely.

**Why**: Deep merge for dicts enables partial overrides (e.g., change one tool's timeout). List replacement is simpler and avoids complex merge semantics (append? prepend? dedupe?).

```yaml
# Global: tools: {brave: {timeout: 60, retries: 3}}
# Project: tools: {brave: {timeout: 120}}
# Result: tools: {brave: {timeout: 120, retries: 3}}
```

### Decision 5: Bootstrap on CLI Startup

**What**: Each CLI's main callback calls `ensure_global_dir(quiet=True)`.

**Why**: Lazy creation on first use is simpler than post-install hooks. The `quiet=True` ensures no output on subsequent runs. Users see the bootstrap message only once.

## Risks / Trade-offs

**Risk**: Accidental inheritance when user wants isolation
- **Mitigation**: `inherit: none` opt-out is explicit and documented

**Risk**: Merge behaviour surprises
- **Mitigation**: Only dicts merge; lists and scalars are replaced

**Risk**: Large bundled defaults increase package size
- **Mitigation**: Current defaults total ~25KB - negligible

**Trade-off**: Implicit inheritance vs explicit
- Chose implicit to match "minimal config should work" principle
- Users who care about isolation will read the docs

## Migration Plan

**No migration required.** The change is backwards compatible:

1. Existing project configs continue to work
2. New `inherit: global` is the default behaviour (same as current when global doesn't exist)
3. Users can opt out with `inherit: none` if needed

**Rollback**: Simply remove the inheritance logic; configs revert to single-file loading.

## Open Questions

None - design is straightforward and implementation is scoped.
