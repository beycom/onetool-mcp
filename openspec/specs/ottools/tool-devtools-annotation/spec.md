# tool-devtools-annotation Specification

## Purpose
Defines the bundled `inject.js` annotation script asset and the `window.__inspector` JavaScript API it exposes. Covers script loading, annotation add/remove/clear operations, and the attribute-based visual highlighting system used by `chrome_util` and `play_util`.
## Requirements
### Requirement: Annotation Script Asset

The system SHALL provide a bundled JavaScript annotation script at `src/ot/assets/inject.js`.

#### Scenario: Script loading
- **GIVEN** the annotation script asset
- **WHEN** loaded via `get_inject_script("inject.js")`
- **THEN** it returns the minified JavaScript as a string
- **AND** the string is suitable for injection via `evaluate_script()`

#### Scenario: Script size
- **GIVEN** the bundled annotation script
- **WHEN** checked
- **THEN** it SHALL be under 100KB

#### Scenario: Generated asset freshness
- **GIVEN** `src/ot/assets/inject-src.js` has been changed
- **WHEN** release checks run
- **THEN** `src/ot/assets/inject.js` SHALL be rebuilt
- **AND** the check SHALL fail if the generated asset differs from the working tree

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
- **WHEN** the internal `dispose()` helper is called by tests or browser adapter cleanup
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
