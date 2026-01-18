# ot-browse Specification

## Purpose

Standalone CLI for fast browser inspection and debugging, optimized for LLM-assisted workflows. Bypasses MCP latency by connecting directly to browser via CDP.
## Requirements
### Requirement: Browser Connection

The CLI SHALL support launching a new Chromium browser or connecting to an existing Chrome instance via CDP.

#### Scenario: Launch new browser
- **WHEN** user runs `ot-browse`
- **THEN** a new Chromium browser instance opens
- **AND** the CLI displays connection status as "Connected"

#### Scenario: Launch and navigate
- **WHEN** user runs `ot-browse https://example.com`
- **THEN** a new browser opens and navigates to the URL
- **AND** the CLI creates a new session

#### Scenario: Connect to existing Chrome
- **WHEN** user selects "Attach to existing" from the menu
- **THEN** the CLI connects to Chrome on the configured CDP port (default 9222)
- **AND** attaches to the first available page

#### Scenario: Connection lost
- **WHEN** the browser is closed or connection drops
- **THEN** the CLI displays "Not connected" status
- **AND** shows the disconnected menu options

### Requirement: Element Annotation

The CLI SHALL allow users to annotate DOM elements with unique IDs and labels for LLM reference.

#### Scenario: Annotate element via browser (Ctrl+I)
- **WHEN** user presses Ctrl+I in the browser
- **AND** clicks an element
- **THEN** a modal dialog prompts for ID and label
- **AND** an `x-inspect` attribute is added to the element
- **AND** the element is highlighted with an orange box and label

#### Scenario: Annotate element via CLI selector
- **WHEN** user selects "Add annotation" and enters a CSS selector
- **AND** the selector matches element(s)
- **THEN** `x-inspect` attributes are added to matched elements
- **AND** IDs are auto-numbered for multiple matches (e.g., h1-1, h1-2, h1-3)

#### Scenario: Predefined annotations
- **GIVEN** annotations defined in ot-browse.yaml
- **WHEN** browser connects or navigates to a new page
- **THEN** predefined annotations are automatically applied

#### Scenario: Annotation format
- **GIVEN** an annotated element
- **THEN** the attribute format is `x-inspect="id:label"` or `x-inspect="id"`
- **AND** CSS selectors can target it as `[x-inspect^="id:"]`

### Requirement: Comprehensive Capture

The CLI SHALL capture page state including annotations, screenshots, HTML, and browser data.

#### Scenario: Capture page
- **WHEN** user selects "Capture page"
- **THEN** a comprehensive capture is saved to the session directory
- **AND** includes: page_info.yaml, annotations.yaml, screenshots/, page.html
- **AND** optionally includes: performance.yaml, accessibility.yaml, images.yaml, network.yaml, console.yaml, cookies.yaml

#### Scenario: Capture content
- **GIVEN** a capture is taken
- **THEN** it includes:
  - Page info: URL, title, viewport, meta tags
  - Browser info: version, user agent, viewport, locale, timezone
  - Screenshots: page.webp and individual annotation screenshots
  - Annotations: id, label, selector, tagName, outerHTML
  - Full page HTML
  - Accessibility tree (ARIA snapshot)
  - Performance metrics (timing, navigation, CDP metrics)
  - Network requests and responses
  - Console messages
  - Cookies

#### Scenario: Screenshot behavior
- **GIVEN** annotations exist on page
- **THEN** main screenshot captures the bounding box around all annotations
- **GIVEN** no annotations exist
- **THEN** main screenshot captures the viewport only

### Requirement: Session Management

The CLI SHALL organize captures into auto-named sessions.

#### Scenario: Create session
- **WHEN** a browser connection is established
- **THEN** a new session is created with timestamp-based name (e.g., 2024-12-30_14-35_session_001)

#### Scenario: Session structure
- **GIVEN** an active session
- **THEN** directory structure is:

  ```text
  .browse/
  └── 2024-12-30_14-35_session_001/
      └── capture_001/
          ├── INDEX.md
          ├── page_info.yaml
          ├── annotations.yaml
          ├── page.html
          ├── screenshots/
          │   ├── page.webp
          │   └── {ann_id}.webp
          ├── performance.yaml
          ├── accessibility.yaml
          ├── images.yaml
          ├── network.yaml
          ├── console.yaml
          └── cookies.yaml
  ```

### Requirement: CLI Navigation

The CLI SHALL provide menu-driven navigation for all operations.

#### Scenario: Disconnected menu

- **GIVEN** no browser connection
- **WHEN** menu is displayed
- **THEN** menu shows: Open URL, Open favorite, Launch browser, Attach to existing, Help, Quit

#### Scenario: Connected menu

- **GIVEN** browser is connected
- **WHEN** menu is displayed
- **THEN** menu shows: Add annotation, List annotations, Remove annotation, Capture page, Session info, Disconnect, Quit

#### Scenario: Browser keybinding

- **GIVEN** browser is connected
- **WHEN** user presses Ctrl+I in browser
- **THEN** element selection mode toggles

### Requirement: Configuration

The CLI SHALL use YAML configuration file.

#### Scenario: Config file location

- **WHEN** no config path specified
- **THEN** looks for ot-browse.yaml in `config/` directory
- **OR** uses OT_BROWSE_CONFIG environment variable

#### Scenario: Config options

- **GIVEN** a config file
- **WHEN** the CLI loads configuration
- **THEN** it can specify:
  - `devtools`: Open DevTools when launching (default: false)
  - `headless`: Run browser in headless mode (default: false)
  - `codegen`: Use Playwright Codegen mode (default: false)
  - `cdp_port`: CDP port for existing browser (default: 9222)
  - `no_viewport`: Allow browser window resize (default: true)
  - `sessions_dir`: Directory for sessions (default: .browse)
  - `screenshot_quality`: WebP quality 1-100 (default: 85)
  - `full_page_screenshot`: Capture full page vs viewport (default: true)
  - `annotation_padding`: Padding around annotation screenshots (default: 50)
  - `browser_args`: Additional browser launch arguments
  - `max_text_length`: Max chars for text in YAML (default: 400, 0 for unlimited)
  - `max_annotation_screenshots`: Skip annotation screenshots if count exceeds this (default: 10, 0 for unlimited)
  - `annotations`: Predefined annotations applied on page load
  - `favorites`: List of favorite URLs (default: empty list)

### Requirement: Session-Level INDEX.md

Each session directory SHALL have an INDEX.md for navigation.

#### Scenario: Session INDEX.md generation
- **GIVEN** a session with multiple captures
- **WHEN** a new capture is created
- **THEN** a session-level INDEX.md is created/updated at `.browse/{session}/INDEX.md`

#### Scenario: Session INDEX.md content
- **GIVEN** a session with 3 captures
- **WHEN** INDEX.md is generated
- **THEN** it includes:
  - Session name and start timestamp
  - Table of captures with: number, URL, title, annotation count, timestamp
  - Quick links to first and latest captures

### Requirement: LLM-Optimized Capture INDEX.md

The INDEX.md generated for each capture SHALL include guidance for LLM consumption.

#### Scenario: Navigation links
- **GIVEN** capture_002 in a session with 3 captures
- **WHEN** INDEX.md is generated
- **THEN** it includes navigation:
  - Previous: link to capture_001/INDEX.md
  - Next: link to capture_003/INDEX.md
  - Session: link to ../INDEX.md

#### Scenario: Task-based guidance section
- **GIVEN** a capture is taken
- **WHEN** INDEX.md is generated
- **THEN** it includes a "How to Use This Capture" section with a task-to-approach table:
  - Get page overview -> Read INDEX.md
  - Find element selectors -> Use page.annotations tool
  - Understand page structure -> Use page.accessibility(filter_type="headings")
  - Find interactive elements -> Use page.accessibility(filter_type="interactive")
  - Search for text -> Use page.search tool
  - Compare with previous -> Use page.diff tool
  - Debug API issues -> Check network.yaml
  - Visual context -> Read screenshots/page.webp

#### Scenario: File sizes displayed
- **GIVEN** a capture with multiple YAML files
- **WHEN** INDEX.md is generated
- **THEN** the files table includes a Size column showing file sizes in human-readable format (KB)

#### Scenario: Large file warnings
- **GIVEN** a capture with aria.yaml > 100KB
- **WHEN** INDEX.md is generated
- **THEN** the aria.yaml entry includes text "**use filtering tool**"
- **AND** page.html entry includes text "**use search tool**"

#### Scenario: Annotations table with line numbers
- **GIVEN** a capture with annotations
- **WHEN** INDEX.md is generated
- **THEN** the annotations table includes columns: ID, Tag, Line, Selector, Screenshot
- **AND** Line column shows line number in page.html
- **AND** selectors are truncated to 50 characters with ellipsis
- **AND** screenshot column shows "[view](screenshots/{id}.webp)" if available, "-" otherwise
- **AND** includes Read command example for context

### Requirement: Enhanced Annotation Data

Annotations SHALL include additional data for LLM accessibility.

#### Scenario: Line number in annotations.yaml
- **GIVEN** an annotation is captured
- **WHEN** annotations.yaml is written
- **THEN** each annotation includes `line_number` field with the line in page.html

#### Scenario: Bounding box in annotations.yaml
- **GIVEN** an annotation is captured
- **WHEN** annotations.yaml is written
- **THEN** each annotation includes `bounding_box` with x, y, width, height

#### Scenario: Computed styles in annotations.yaml
- **GIVEN** an annotation is captured
- **WHEN** annotations.yaml is written
- **THEN** each annotation includes `computed_styles` with key visual properties:
  - display, position, visibility
  - color, backgroundColor
  - fontSize, fontWeight
  - width, height

### Requirement: Favorite URLs

The CLI SHALL support a configurable list of favorite URLs for quick access.

#### Scenario: Open favorite menu item

- **GIVEN** favorites are configured in ot-browse.yaml
- **WHEN** user is on the disconnected menu
- **THEN** "Open favorite" appears as a menu option with shortcut key "f"

#### Scenario: Select favorite URL

- **WHEN** user selects "Open favorite"
- **THEN** a picker displays all configured URLs
- **AND** user can select a URL to open

#### Scenario: Open selected favorite

- **WHEN** user selects a URL from the favorites picker
- **THEN** the browser launches and navigates to that URL
- **AND** a new session is created

#### Scenario: No favorites configured

- **GIVEN** no favorites in configuration
- **WHEN** user selects "Open favorite"
- **THEN** a message indicates no favorites are configured
