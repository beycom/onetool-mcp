# browse-logging Specification

## Purpose

Defines browser session logging, navigation logging, and interaction logging for ot-browse.

---

## Requirements

### Requirement: Browser Session Logging

The system SHALL log browser session lifecycle events.

#### Scenario: Session start logging
- **GIVEN** a browser session is initialized
- **WHEN** the session starts
- **THEN** it SHALL log:
  - `span: "browse.session.start"`
  - `url`: Initial URL
  - `headless`: Boolean for headless mode
  - `viewport`: Viewport dimensions

#### Scenario: Session stop logging
- **GIVEN** a browser session is active
- **WHEN** the session ends
- **THEN** it SHALL log:
  - `span: "browse.session.stop"`
  - `duration`: Session duration in seconds
  - `pagesVisited`: Count of pages navigated

### Requirement: Navigation Logging

The system SHALL log page navigation events.

#### Scenario: Page navigation success
- **GIVEN** a navigation request is made
- **WHEN** navigation completes successfully
- **THEN** it SHALL log:
  - `span: "browse.navigate"`
  - `url`: Target URL
  - `status`: HTTP status code
  - `loadTime`: Page load time in seconds
  - `duration`: Navigation duration

#### Scenario: Navigation failure
- **GIVEN** a navigation request is made
- **WHEN** navigation fails
- **THEN** it SHALL log:
  - `span: "browse.navigate"`
  - `url`: Target URL
  - `status: "FAILED"`
  - `errorType`: Error class name
  - `errorMessage`: Error details

### Requirement: Screenshot Logging

The system SHALL log screenshot capture events.

#### Scenario: Screenshot capture
- **GIVEN** a screenshot request is made
- **WHEN** the screenshot is captured
- **THEN** it SHALL log:
  - `span: "browse.screenshot"`
  - `path`: Output file path
  - `width`: Image width
  - `height`: Image height
  - `size`: File size in bytes
  - `duration`: Capture duration

### Requirement: Element Interaction Logging

The system SHALL log element interactions.

#### Scenario: Element find
- **GIVEN** an element lookup is performed
- **WHEN** the lookup completes
- **THEN** it SHALL log:
  - `span: "browse.element.find"`
  - `selector`: CSS or XPath selector
  - `found`: Boolean indicating success
  - `count`: Number of matching elements

#### Scenario: Element click
- **GIVEN** a click action is performed
- **WHEN** the click completes
- **THEN** it SHALL log:
  - `span: "browse.element.click"`
  - `selector`: Element selector
  - `success`: Boolean indicating success

#### Scenario: Element type
- **GIVEN** text input is performed
- **WHEN** the input completes
- **THEN** it SHALL log:
  - `span: "browse.element.type"`
  - `selector`: Element selector
  - `length`: Character count (not the actual text)

### Requirement: State Persistence Logging

The system SHALL log browser state save/load operations.

#### Scenario: State save
- **GIVEN** browser state is saved
- **WHEN** the save completes
- **THEN** it SHALL log:
  - `span: "browse.state.save"`
  - `path`: State file path
  - `cookies`: Cookie count
  - `localStorage`: Local storage key count

#### Scenario: State load
- **GIVEN** browser state is restored
- **WHEN** the load completes
- **THEN** it SHALL log:
  - `span: "browse.state.load"`
  - `path`: State file path
  - `success`: Boolean indicating success
