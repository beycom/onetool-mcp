## ADDED Requirements

### Requirement: Pack registration and aliases

The whiteboard pack SHALL be registered under the full pack name `whiteboard` and SHALL be reachable via two declared aliases: `wb` and `excalidraw`, both present in `pack_aliases` beside the `pack = "whiteboard"` declaration in `src/otdev/tools/excalidraw.py`. All three prefixes (`whiteboard.`, `wb.`, `excalidraw.`) SHALL resolve to the identical set of pack tools.

#### Scenario: Full pack name resolves
- **WHEN** a user calls `whiteboard.draw(input='box:A')`
- **THEN** the call is routed to the whiteboard pack's `draw` tool

#### Scenario: wb short alias resolves
- **WHEN** a user calls `wb.draw(input='box:A')`
- **THEN** the call is routed to the whiteboard pack's `draw` tool, identically to `whiteboard.draw(input='box:A')`

#### Scenario: excalidraw alias resolves
- **WHEN** a user calls `excalidraw.draw(input='box:A')` (or any other whiteboard tool via the `excalidraw.` prefix, e.g. `excalidraw.save(...)`, `excalidraw.open()`, `excalidraw.close()`)
- **THEN** the call is routed to the whiteboard pack's tool of the same name, identically to `whiteboard.draw(input='box:A')` and `wb.draw(input='box:A')`

#### Scenario: excalidraw alias is only injected when the whiteboard pack is loaded
- **WHEN** the whiteboard pack is not loaded (e.g. `[dev]` extra not installed)
- **THEN** `excalidraw` SHALL NOT appear in the execution namespace, consistent with how `wb` is only injected when `whiteboard` is loaded
