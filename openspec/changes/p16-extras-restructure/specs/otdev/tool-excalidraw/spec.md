## ADDED Requirements

### Requirement: [util] install extra

The package SHALL provide the `pydoll-python` dependency that the `whiteboard` pack requires as part
of the `[util]` optional-dependency group in `pyproject.toml` (NOT a standalone `whiteboard` extra).
Installing `onetool-mcp[util]` — or `onetool-mcp[all]`, which includes `[util]` — SHALL make
`pydoll-python` importable, and therefore make `whiteboard.*` tools usable. There SHALL be no
standalone `whiteboard` optional-dependency group; `pip install 'onetool-mcp[whiteboard]'` SHALL fail
with "no such extra" since that extra name no longer exists (V3 breaking change, no compatibility
shim).

If `pydoll-python` is not importable when a whiteboard tool tries to launch the browser, the tool
SHALL raise `ImportError` with the message `"pydoll-python is required for whiteboard. Install with:
pip install 'onetool-mcp[util]'"`.

#### Scenario: [util] extra provides pydoll-python
- **WHEN** `onetool-mcp[util]` is installed
- **THEN** `import pydoll` SHALL succeed in that environment

#### Scenario: [all] extra provides pydoll-python
- **WHEN** `onetool-mcp[all]` is installed
- **THEN** `import pydoll` SHALL succeed in that environment (because `[all]` includes `[util]`)

#### Scenario: Missing pydoll raises install error pointing at [util]
- **WHEN** a whiteboard tool attempts to launch the browser and `pydoll-python` is not importable
- **THEN** the tool SHALL raise `ImportError` with message: `"pydoll-python is required for
  whiteboard. Install with: pip install 'onetool-mcp[util]'"`

#### Scenario: [whiteboard] extra no longer exists
- **WHEN** `pip install 'onetool-mcp[whiteboard]'` (or the equivalent `uv tool install`) is run
  against this package
- **THEN** the install SHALL fail because no `whiteboard` optional-dependency group is defined
- **AND** there SHALL be no code path that falls back to or emulates the removed extra

### Requirement: Chrome launch suppresses on-device model download

When the `whiteboard` pack launches Chrome via pydoll (`src/otdev/tools/excalidraw.py`, the
`_open_browser()` internal function), it SHALL pass a `pydoll.browser.options.ChromiumOptions`
instance to `Chrome(options=...)` with the following command-line arguments added, so that a plain
Chrome launch does not trigger background downloads or networking the user did not ask for:

- `--disable-features=OptimizationGuideOnDeviceModel,OnDeviceModelBackgroundDownload`
- `--disable-component-update`
- `--disable-background-networking`

`Chrome()` SHALL NOT be constructed with no options (i.e. `Chrome()` with zero arguments is no longer
a valid launch call for this pack).

#### Scenario: Chrome is launched with suppression flags
- **WHEN** the whiteboard pack launches Chrome (any call path that reaches `_open_browser()`, e.g.
  the first call to `whiteboard.open()` in a session)
- **THEN** `Chrome` SHALL be constructed with an `options=` keyword argument
- **AND** that `ChromiumOptions` instance's `arguments` list SHALL contain all three flags:
  `--disable-features=OptimizationGuideOnDeviceModel,OnDeviceModelBackgroundDownload`,
  `--disable-component-update`, `--disable-background-networking`

#### Scenario: Retry attempts preserve suppression flags
- **WHEN** the initial Chrome launch fails with `NoValidTabFound` and `_open_browser()` retries (up to
  3 attempts total)
- **THEN** every retry attempt's `Chrome(...)` call SHALL also include the same suppression flags —
  no retry path SHALL fall back to a bare `Chrome()` call
