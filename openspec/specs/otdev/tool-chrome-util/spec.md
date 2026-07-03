# tool-chrome-util Specification

## Purpose
Defines the `chrome_util` (`chrome`) tool pack, which exposes programmatic
annotation utilities through a Chrome DevTools-compatible MCP server.

## Requirements
### Requirement: chrome_util Pack Declaration

The system SHALL provide a `chrome_util` tool pack with `chrome` as a short alias.

#### Scenario: Pack discovery
- **GIVEN** the `otdev` extra is installed
- **WHEN** tools are discovered
- **THEN** the `chrome_util` pack SHALL expose `inject_annotations`, `highlight_element`, `scan_annotations`, `clear_annotations`, and `guide_user`
- **AND** callers MAY use the `chrome` alias

### Requirement: Annotation Injection

The `chrome_util` pack SHALL provide an `inject_annotations()` function for one-time page setup.

#### Scenario: Successful injection
- **GIVEN** a browser page is open via DevTools MCP
- **WHEN** `chrome_util.inject_annotations()` is called
- **THEN** the inject.js script is loaded into the page
- **AND** the result includes `success: True`, `ready: True`, and `version`

#### Scenario: Already injected
- **GIVEN** inject.js is already loaded on the page
- **WHEN** `chrome_util.inject_annotations()` is called again
- **THEN** it returns success without re-injecting (idempotent)

### Requirement: Element Highlighting

The `chrome_util` pack SHALL provide a `highlight_element()` function for programmatic annotation.

#### Scenario: Highlight single element
- **GIVEN** inject.js is loaded on the page
- **WHEN** `chrome_util.highlight_element(selector="button.submit", label="Click here")` is called
- **THEN** the element is visually highlighted with an orange border and label
- **AND** the result includes `success`, `count`, and `ids`

#### Scenario: Highlight with colour
- **GIVEN** inject.js is loaded on the page
- **WHEN** `chrome_util.highlight_element(selector=".error", label="Error", color="red")` is called
- **THEN** the element is highlighted using the red colour scheme

#### Scenario: No matching elements
- **GIVEN** inject.js is loaded on the page
- **WHEN** `chrome_util.highlight_element(selector=".nonexistent", label="Test")` is called
- **THEN** the result includes `success: False` and `count: 0`

### Requirement: Annotation Scanning

The `chrome_util` pack SHALL provide a `scan_annotations()` function to read all annotations.

#### Scenario: Scan existing annotations
- **GIVEN** elements have been annotated (programmatically or by user via Ctrl+I with custom labels)
- **WHEN** `chrome_util.scan_annotations()` is called
- **THEN** it returns a list of dicts with `id`, `label`, `selector`, `content`, `tagName`, and `color`

#### Scenario: No annotations
- **GIVEN** no elements are annotated
- **WHEN** `chrome_util.scan_annotations()` is called
- **THEN** it returns an empty list

### Requirement: Annotation Clearing

The `chrome_util` pack SHALL provide a `clear_annotations()` function to remove all annotations.

#### Scenario: Clear all annotations
- **GIVEN** multiple elements are annotated
- **WHEN** `chrome_util.clear_annotations()` is called
- **THEN** all `x-inspect` and `x-inspect-color` attributes are removed
- **AND** all visual highlights are cleared
- **AND** the result includes `success: True` and the count of cleared annotations

### Requirement: Guided User Workflow

The `chrome_util` pack SHALL provide a `guide_user()` function for sequential element highlighting.

#### Scenario: Sequential step highlighting
- **GIVEN** inject.js is loaded on the page
- **WHEN** `chrome_util.guide_user(task="Fill form", steps=[{"selector": "input[name='name']", "label": "Enter name"}, {"selector": "button[type='submit']", "label": "Submit"}])` is called
- **THEN** each step's element is highlighted in sequence
- **AND** each step uses the specified colour (defaulting to orange)

### Requirement: Server Independence

The `chrome_util` pack SHALL use a Chrome DevTools-compatible MCP server selected by an optional keyword-only `server` argument. When omitted, `server` SHALL default to `chrome_devtools`.

#### Scenario: Selected server required
- **GIVEN** the selected server is not connected
- **WHEN** any chrome_util function is called
- **THEN** it returns an error indicating the selected server name is unavailable
- **AND** it lists available servers in the error message

#### Scenario: Compatible server override
- **GIVEN** a Chrome DevTools-compatible server is connected under a non-default name
- **WHEN** `chrome_util.inject_annotations(server="chrome_devtool_connect")` is called
- **THEN** it SHALL call that server's `evaluate_script` tool.
