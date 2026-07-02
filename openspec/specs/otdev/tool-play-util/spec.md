# tool-play-util Specification

## Purpose
Defines the `play_util` (`play`) tool pack and the shared `inject.js` browser
annotation behavior it exposes through the Playwright MCP server.

## Requirements
### Requirement: play_util Pack Declaration

The system SHALL provide a `play_util` tool pack with `play` as a short alias.

#### Scenario: Pack discovery
- **GIVEN** the `otdev` extra is installed
- **WHEN** tools are discovered
- **THEN** the `play_util` pack SHALL expose `inject_annotations`, `enable_auto_inject`, `highlight_element`, `scan_annotations`, `clear_annotations`, and `guide_user`
- **AND** callers MAY use the `play` alias

### Requirement: Annotation Script Asset

The system SHALL provide a bundled JavaScript annotation script through
`ot.assets`.

#### Scenario: Script loading
- **GIVEN** the annotation script asset
- **WHEN** `play_util.inject_annotations()` is called
- **THEN** it SHALL inject the bundled script through the Playwright MCP server

### Requirement: Annotation API

The injected script SHALL expose a `window.__inspector` API for programmatic annotation management.

#### Scenario: Add annotation
- **GIVEN** `window.__inspector` is available
- **WHEN** `addAnnotation(selector, id, label, color)` is called
- **THEN** matching elements receive `x-inspect` and `x-inspect-color` attributes
- **AND** visual highlights are rendered immediately
- **AND** the result includes `success`, `count`, and `ids` fields

#### Scenario: Scan annotations
- **GIVEN** elements with `x-inspect` attributes
- **WHEN** `scanAnnotations()` is called
- **THEN** it returns an array of objects with `id`, `label`, `selector`, `content`, `tagName`, and `color`

#### Scenario: Remove annotation
- **GIVEN** an annotated element
- **WHEN** `removeAnnotation(selector)` is called
- **THEN** the `x-inspect` and `x-inspect-color` attributes are removed
- **AND** the visual highlight is cleared

#### Scenario: Ready check
- **GIVEN** the script has been injected
- **WHEN** `isReady()` is called
- **THEN** it returns `true`

#### Scenario: Internal cleanup
- **GIVEN** the script has been injected
- **WHEN** the browser-side `dispose()` API is called
- **THEN** annotation attributes, overlays, global listeners, and observers are removed
- **AND** the script can be injected again successfully

### Requirement: Colour Coding

The annotation system SHALL support four colour schemes for visual categorisation.

#### Scenario: Default orange highlights
- **GIVEN** an annotation added without specifying colour
- **WHEN** rendered
- **THEN** it uses the orange colour scheme (#f59e0b border)

#### Scenario: Named colour highlights
- **GIVEN** an annotation added with colour "red", "blue", or "green"
- **WHEN** rendered
- **THEN** it uses the corresponding colour scheme

### Requirement: SPA Navigation Support

The annotation system SHALL survive client-side navigation in single-page applications.

#### Scenario: DOM mutation detection
- **GIVEN** the annotation script is injected
- **WHEN** significant DOM changes occur (more than 5 added nodes)
- **THEN** highlights are re-rendered after a 100ms debounce

### Requirement: Smart Label Positioning

The annotation system SHALL position labels to remain visible within the viewport.

#### Scenario: Label above element
- **GIVEN** an annotated element with sufficient space above
- **WHEN** the highlight is rendered
- **THEN** the label appears above the element

#### Scenario: Label flipped below
- **GIVEN** an annotated element near the top of the viewport (less than 20px)
- **WHEN** the highlight is rendered
- **THEN** the label appears below the element

#### Scenario: Label horizontal clamping
- **GIVEN** an annotated element near the right edge of the viewport
- **WHEN** the highlight is rendered
- **THEN** the label is clamped to remain within the viewport

### Requirement: Manual Selection Mode

The annotation system SHALL support a manual element selection mode via keyboard shortcut.

#### Scenario: Toggle selection mode
- **GIVEN** the annotation script is injected
- **WHEN** the user presses Ctrl+I (or Cmd+I on macOS)
- **THEN** selection mode is toggled
- **AND** the cursor changes to crosshair
- **AND** hovering over elements shows a dashed orange preview

#### Scenario: Create annotation with custom label
- **GIVEN** selection mode is active
- **WHEN** the user clicks an element
- **THEN** a prompt dialog appears asking for an annotation name
- **AND** the prompt shows the element's tag name as default
- **AND** if the user enters a label, the annotation is created with that label
- **AND** if the user enters nothing, the annotation is created with the tag name
- **AND** if the user cancels, selection mode exits without creating an annotation

### Requirement: Performance Optimisation

The annotation system SHALL optimise rendering for scroll and resize events.

#### Scenario: Debounced scroll updates
- **GIVEN** annotated elements on the page
- **WHEN** the user scrolls
- **THEN** highlights are re-rendered after a 150ms debounce using requestAnimationFrame

#### Scenario: Debounced resize updates
- **GIVEN** annotated elements on the page
- **WHEN** the viewport is resized
- **THEN** highlights are re-rendered after a 150ms debounce using requestAnimationFrame

### Requirement: Playwright Server Boundary

The `play_util` pack SHALL use the configured `playwright` MCP server.

#### Scenario: Playwright server required
- **GIVEN** the `playwright` MCP server is not connected
- **WHEN** any `play_util` function is called
- **THEN** it SHALL return an error indicating the `playwright` server is unavailable
- **AND** include the available server names in the error message

#### Scenario: Auto-inject registration
- **GIVEN** the `playwright` MCP server is connected
- **WHEN** `play_util.enable_auto_inject()` is called
- **THEN** it SHALL register the annotation script for future pages in the browser session
- **AND** return `success` and `auto_inject` fields
