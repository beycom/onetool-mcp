# tool-page-view Specification

## Purpose

Provides LLM-friendly tools for analyzing browse session captures from `onetool-browse`. These tools enable navigation, annotation inspection, search, and comparison of page captures stored in `.onetool/sessions/` directories.
## Requirements
### Requirement: Page View List Tool

The `page.list` tool SHALL list available page views.

#### Scenario: List all sessions
- **GIVEN** a `.onetool/sessions/` directory with 3 sessions
- **WHEN** `page.list()` is called
- **THEN** it returns a list of sessions with:
  - Session name/path
  - Number of captures
  - First capture timestamp
  - Latest capture URL and title

#### Scenario: Output format
- **GIVEN** sessions in .onetool/sessions/
- **WHEN** `page.list()` is called
- **THEN** output is formatted as:

  ```text
  # Page Views

  | Session | Captures | Started | Latest URL |
  |---------|----------|---------|------------|
  | 2025-12-31_22-46_session_001 | 3 | 22:46 | https://example.com |
  | 2025-12-31_23-15_session_002 | 1 | 23:15 | https://other.com |

  Use page.captures(session_id="001") to list captures.
  ```

#### Scenario: No sessions
- **GIVEN** an empty .onetool/sessions/ directory
- **WHEN** `page.list()` is called
- **THEN** it returns "No sessions found in: {path}"

#### Scenario: Custom sessions directory
- **GIVEN** sessions in a custom directory
- **WHEN** `page.list(sessions_dir="/custom/path")` is called
- **THEN** it lists sessions from that directory

#### Scenario: Project-based discovery
- **GIVEN** project "onetool" configured with path "/path/to/onetool"
- **WHEN** `page.list(project="onetool")` is called
- **THEN** it lists sessions from "/path/to/onetool/.browse"

#### Scenario: Default sessions directory resolution
- **GIVEN** no explicit sessions_dir or project specified
- **AND** config `tools.page_view.sessions_dir` is `".onetool/sessions"` (default)
- **WHEN** `page.list()` is called
- **THEN** it resolves `.onetool/sessions` relative to project working directory (`OT_CWD` or cwd)
- **AND** falls back to home directory if not found in project

### Requirement: Page View Captures Tool

The `page.captures` tool SHALL list captures within a session.

#### Scenario: List captures in session
- **GIVEN** a session with 3 captures
- **WHEN** `page.captures(session_id="001")` is called
- **THEN** it returns a list of captures with:
  - Capture number
  - URL and title
  - Annotation count
  - Timestamp
  - Path to INDEX.md

#### Scenario: Output format
- **GIVEN** captures in a session
- **WHEN** `page.captures` is called
- **THEN** output is formatted as:

  ```text
  # Session: 2025-12-31_22-46_session_001

  | # | URL | Title | Annotations | Time |
  |---|-----|-------|-------------|------|
  | 1 | https://example.com | Home | 3 | 22:46:48 |
  | 2 | https://example.com/login | Login | 5 | 22:47:12 |
  | 3 | https://example.com/dashboard | Dashboard | 2 | 22:48:30 |

  Use page.annotations(session_id="001", capture_id="001") to view annotations.
  ```

#### Scenario: Session not found
- **GIVEN** a non-existent session pattern
- **WHEN** `page.captures` is called
- **THEN** it returns "No session matches '{pattern}'. Available: ..."

### Requirement: Page View Annotations Tool

The `page.annotations` tool SHALL provide quick access to all user-marked annotations with enhanced data including line numbers, positions, and visual properties.

#### Scenario: List all annotations
- **GIVEN** a capture with 3 annotations (h1, p-1, p-2)
- **WHEN** `page.annotations(session_id="001", capture_id="001")` is called
- **THEN** it returns all annotations with:
  - id, label, selector, tagName
  - Line number in page.html
  - outerHTML (truncated to 500 chars)
  - Screenshot path if available

#### Scenario: Display line number from annotations.yaml
- **GIVEN** annotations.yaml contains `line_number` field
- **WHEN** `page.annotations(session_id="001", capture_id="001")` is called
- **THEN** each annotation shows "Line: {N} in page.html"
- **AND** includes Read command example with offset based on line number

#### Scenario: Display bounding box when available
- **GIVEN** annotations.yaml contains `bounding_box` field
- **WHEN** `page.annotations` is called
- **THEN** each annotation shows "Position: {x},{y} Size: {width}x{height}"

#### Scenario: Display computed styles summary
- **GIVEN** annotations.yaml contains `computed_styles` field
- **WHEN** `page.annotations` is called
- **THEN** each annotation shows key styles (display, color, fontSize) on one line

#### Scenario: Output format with line numbers
- **GIVEN** annotations in a capture
- **WHEN** `page.annotations` is called
- **THEN** output is formatted as:

  ```text
  # Annotations: capture_001

  Found 3 annotation(s)

  ## h1 (heading-1)
  - Tag: h1
  - Selector: #firstHeading
  - Line: 7152 in page.html
  - Screenshot: screenshots/h1.webp (use Read tool to view)
  - HTML: <h1 id="firstHeading">...</h1>

  To read context: Read(file_path="...page.html", offset=7145, limit=20)
  To view screenshot: Read(file_path="...screenshots/h1.webp")
  ```

#### Scenario: No annotations
- **GIVEN** a capture with no annotations
- **WHEN** `page.annotations` is called
- **THEN** it returns "No annotations found in: {capture_path}"

#### Scenario: Capture required
- **GIVEN** a session with captures 001, 002, 003
- **WHEN** `page.annotations(session_id="001", capture_id="001")` is called
- **THEN** it returns annotations from the specified capture

### Requirement: Page View Context Tool

The `page.context` tool SHALL provide page structure around a specific annotation with line numbers.

#### Scenario: Get context for annotation
- **GIVEN** an annotation with id "h1" and selector "#firstHeading"
- **WHEN** `page.context(session_id="001", capture_id="001", annotation_id="h1")` is called
- **THEN** it returns:
  - The annotation details (selector, tag, HTML)
  - Line number in page.html where element appears
  - Accessibility tree context: parent landmarks and siblings
  - HTML context: surrounding elements with line numbers
  - Screenshot path for visual reference

#### Scenario: Line number reference
- **GIVEN** an annotation at line 7152 of page.html
- **WHEN** context is requested
- **THEN** output includes:

  ```text
  ## Location
  - File: page.html
  - Line: 7152
  - Read context: Read(file_path="...page.html", offset=7145, limit=20)

  ## Visual
  - Screenshot: screenshots/h1.webp
  - View: Read(file_path="...screenshots/h1.webp")
  ```

#### Scenario: Accessibility context extraction
- **GIVEN** an annotation with selector "#firstHeading"
- **WHEN** context is requested
- **THEN** accessibility context includes:
  - Parent landmark regions (banner, main, article)
  - Sibling elements at same level
  - Nearby headings for document structure
- **AND** output is limited to relevant elements (not full tree)

#### Scenario: HTML context extraction
- **GIVEN** an annotation with selector "#firstHeading"
- **WHEN** context is requested with `include_html=True`
- **THEN** HTML context includes:
  - The annotated element's full HTML with line number
  - Parent container (up to 2 levels) with line numbers
  - Sibling elements (prev 2, next 2) with line numbers
- **AND** each element is truncated to 1000 chars

#### Scenario: Annotation not found
- **GIVEN** a capture without annotation "foo"
- **WHEN** `page.context(annotation_id="foo")` is called
- **THEN** it returns "Annotation 'foo' not found. Available: h1, p-1, p-2"

### Requirement: Page View Search Tool

The `page.search` tool SHALL search within HTML and accessibility tree, returning line numbers.

#### Scenario: Search HTML
- **GIVEN** a page.html with 8677 lines
- **WHEN** `page.search(session_id="001", capture_id="001", pattern="x-inspect", search_in="html")` is called
- **THEN** it returns matching lines with line numbers:

  ```text
  # Search: `x-inspect`

  Capture: capture_001
  Searched: html
  Found: 3 match(es)

  | File | Line | Content |
  |------|------|---------|
  | page.html | 7152 | `<h1 id="firstHeading" x-inspect="h1:heading-1">` |
  | page.html | 7464 | `<p x-inspect="p-1"><b>OpenAI</b> is an American...` |
  ```

#### Scenario: Search accessibility tree
- **GIVEN** an aria.yaml file
- **WHEN** `page.search(session_id="001", capture_id="001", pattern="button", search_in="accessibility")` is called
- **THEN** it returns matching ARIA elements with context

#### Scenario: Search both (default)
- **GIVEN** a capture with both page.html and accessibility.yaml
- **WHEN** `page.search(session_id="001", capture_id="001", pattern="OpenAI")` is called without search_in
- **THEN** it searches both files and returns combined results (search_in="both" is default)

#### Scenario: Limit results
- **GIVEN** a pattern matching 100+ lines
- **WHEN** `page.search(session_id="001", capture_id="001", pattern="div", max_results=10)` is called
- **THEN** it returns first 10 matches

### Requirement: Page View Diff Tool

The `page.diff` tool SHALL compare two captures to show what changed.

#### Scenario: Compare two captures
- **GIVEN** a session with capture_001 and capture_002
- **WHEN** `page.diff(session_id="001", capture_id_1="001", capture_id_2="002")` is called
- **THEN** it returns a diff showing:
  - URL/title changes
  - Annotations added/removed/changed
  - Accessibility tree changes (summary)
  - New network requests

#### Scenario: Diff output format
- **GIVEN** two captures with differences
- **WHEN** `page.diff` is called
- **THEN** output is formatted as:

  ```text
  # Diff: capture_001 → capture_002

  ## Summary
  - URL: https://example.com → https://example.com/login
  - Title: "Home" → "Login"
  - Annotations: 3 → 5 (+2 added)

  ## Annotations

  ### Added
  - login-btn: button#submit (line 245)
  - username: input#user (line 198)

  ### Removed
  - (none)

  ## Accessibility Changes

  ### Added Elements
  - form "Login form"
    - textbox "Username"
    - textbox "Password"
    - button "Sign In"

  ### Removed Elements
  - region "Welcome banner"

  ## Network Requests (new)
  - POST /api/auth/check
  - GET /api/user/session
  ```

#### Scenario: No changes
- **GIVEN** two identical captures
- **WHEN** `page.diff` is called
- **THEN** it returns "No differences between capture_001 and capture_002"

#### Scenario: Compare captures in same session
- **GIVEN** captures in the same session
- **WHEN** `page.diff(session_id="001", capture_id_1="001", capture_id_2="002")` is called
- **THEN** it compares the two captures within that session

### Requirement: Page View Summary Tool

The `page.summary` tool SHALL provide a quick overview of a page capture with file size guidance for LLMs.

#### Scenario: Get capture summary
- **GIVEN** a page view at `.onetool/sessions/2025-12-31_22-46_session_001`
- **WHEN** `page.summary(session_id="001", capture_id="001")` is called
- **THEN** it returns a markdown summary including:
  - Page URL and title
  - Viewport dimensions
  - Annotation count with IDs, tags, and selectors
  - Network request counts (total, API, failed)
  - Performance timing (load time)
  - Screenshot path for visual reference
  - File paths for detailed inspection

#### Scenario: Warn about large accessibility file
- **GIVEN** accessibility.yaml is larger than 100KB
- **WHEN** `page.summary` is called
- **THEN** the file entry shows "use page.accessibility with filter"

#### Scenario: Warn about large HTML file
- **GIVEN** page.html is larger than 500KB
- **WHEN** `page.summary` is called
- **THEN** the file entry shows "use page.search"

#### Scenario: Capture ID required
- **GIVEN** a session with captures 001, 002, 003
- **WHEN** `page.summary(session_id="001", capture_id="001")` is called
- **THEN** it returns summary for the specified capture

#### Scenario: Session not found
- **GIVEN** a non-existent session path
- **WHEN** `page.summary` is called
- **THEN** it returns an error message: "Session not found: {path}"

### Requirement: Page View Accessibility Tool

The `page.accessibility` tool SHALL provide filtered access to the ARIA accessibility tree.

#### Scenario: Filter to interactive elements
- **GIVEN** a capture with aria.yaml containing buttons, links, inputs
- **WHEN** `page.accessibility(session_id="001", capture_id="001", filter_type="interactive")` is called
- **THEN** it returns only button, link, checkbox, radio, textbox, searchbox, combobox, slider, switch elements

#### Scenario: Filter to headings
- **GIVEN** a capture with aria.yaml containing h1-h6 elements
- **WHEN** `page.accessibility(session_id="001", capture_id="001", filter_type="headings")` is called
- **THEN** it returns heading elements showing page outline structure

#### Scenario: Filter to forms
- **GIVEN** a capture with aria.yaml containing form elements
- **WHEN** `page.accessibility(session_id="001", capture_id="001", filter_type="forms")` is called
- **THEN** it returns form, textbox, checkbox, radio, combobox, listbox elements

#### Scenario: Filter to links
- **GIVEN** a capture with aria.yaml containing links
- **WHEN** `page.accessibility(session_id="001", capture_id="001", filter_type="links")` is called
- **THEN** it returns link elements with their URLs

#### Scenario: Filter to landmarks
- **GIVEN** a capture with aria.yaml containing landmark regions
- **WHEN** `page.accessibility(session_id="001", capture_id="001", filter_type="landmarks")` is called
- **THEN** it returns banner, main, navigation, complementary, contentinfo, region elements

#### Scenario: Limit output lines
- **GIVEN** an accessibility tree with many matching elements
- **WHEN** `page.accessibility(session_id="001", capture_id="001", max_lines=50)` is called
- **THEN** it returns at most 50 matching lines (default 200)

#### Scenario: Size reduction
- **GIVEN** an aria.yaml of 258KB
- **WHEN** any filter is applied
- **THEN** the output SHALL be less than 15KB

### Requirement: Tool Interface

Tools SHALL follow existing onetool conventions with simplified parameters.

#### Scenario: Keyword-only arguments
- **GIVEN** any page.* function
- **THEN** all arguments SHALL be keyword-only (using `*`)
- **EXAMPLE** `page.annotations(session_id="001", capture_id="001")`

#### Scenario: Parameter naming
- **GIVEN** any page.* function
- **THEN** session identifier parameter SHALL be named `session_id`
- **AND** capture identifier parameter SHALL be named `capture_id`
- **AND** diff tool capture parameters SHALL be named `capture_id_1` and `capture_id_2`
- **AND** `project` parameter SHALL be available on all tools

#### Scenario: Return format
- **GIVEN** any page view tool
- **WHEN** called successfully
- **THEN** it returns a string formatted as markdown

#### Scenario: Screenshot references
- **GIVEN** any page view tool that references screenshots
- **THEN** it SHALL include the full path to the screenshot file
- **AND** note that LLMs with vision capability can use `Read(file_path="...")` to view images

#### Scenario: Error handling
- **GIVEN** any page view tool
- **WHEN** an error occurs (file not found, parse error)
- **THEN** it returns a string starting with "Error: "

### Requirement: Project-Based Session Resolution

Tools SHALL resolve `.browse` directories from configured projects.

#### Scenario: Resolve from project name
- **GIVEN** `ot-serve.yaml` contains `projects: { onetool: /path/to/onetool }`
- **WHEN** `page.list(project="onetool")` is called
- **THEN** it lists sessions from `/path/to/onetool/.onetool/sessions`

#### Scenario: Project not found
- **GIVEN** no project named "foo" is configured
- **WHEN** `page.list(project="foo")` is called
- **THEN** it returns error "Project 'foo' not found. Available: onetool, myapp"

#### Scenario: Sessions dir override
- **GIVEN** both `project` and `sessions_dir` are specified
- **WHEN** a tool is called
- **THEN** `sessions_dir` takes precedence over `project`

#### Scenario: Default behavior without project
- **GIVEN** neither `project` nor `sessions_dir` is specified
- **WHEN** a tool is called
- **THEN** it uses current directory or home directory (existing behavior)

### Requirement: Partial Session Matching

Tools SHALL support partial session ID matching via the `session_id` parameter.

#### Scenario: Match session by suffix
- **GIVEN** sessions: `2025-12-31_22-46_session_001`, `2025-12-31_23-15_session_002`
- **WHEN** `page.captures(session_id="001")` is called
- **THEN** it matches `2025-12-31_22-46_session_001`

#### Scenario: Match session by time pattern
- **GIVEN** sessions: `2025-12-31_22-46_session_001`, `2025-12-31_23-15_session_002`
- **WHEN** `page.captures(session_id="22-46")` is called
- **THEN** it matches `2025-12-31_22-46_session_001`

#### Scenario: Ambiguous session match
- **GIVEN** sessions: `session_001`, `session_001a`
- **WHEN** `page.captures(session_id="001")` is called
- **THEN** it returns error "Multiple sessions match '001': session_001, session_001a. Be more specific."

#### Scenario: No session match
- **GIVEN** sessions: `session_001`, `session_002`
- **WHEN** `page.captures(session_id="999")` is called
- **THEN** it returns error "No session matches '999'. Available: session_001, session_002"

#### Scenario: Exact match takes precedence
- **GIVEN** sessions: `session_001`, `session_0012`
- **WHEN** `page.captures(session_id="session_001")` is called
- **THEN** it matches exactly `session_001` (not treated as ambiguous)

### Requirement: Partial Capture Matching

Tools SHALL support partial capture ID matching via the `capture_id` parameter.

#### Scenario: Match capture by number
- **GIVEN** captures: `capture_001`, `capture_002`, `capture_003`
- **WHEN** `page.annotations(session_id="001", capture_id="002")` is called
- **THEN** it matches `capture_002`

#### Scenario: Match capture by pattern
- **GIVEN** captures: `capture_001`, `capture_special`
- **WHEN** `page.annotations(session_id="001", capture_id="special")` is called
- **THEN** it matches `capture_special`

#### Scenario: No capture match
- **GIVEN** captures: `capture_001`, `capture_002`
- **WHEN** `page.annotations(session_id="001", capture_id="999")` is called
- **THEN** it returns error "No capture matches '999'. Available: capture_001, capture_002"

### Requirement: Page View Logging

The tool SHALL log browser operations using LogSpan.

#### Scenario: Page navigation logging
- **GIVEN** a page navigation is requested
- **WHEN** navigation completes
- **THEN** it SHALL log:
  - `span: "page.navigate"`
  - `url`: Target URL
  - `status`: HTTP status code

#### Scenario: Screenshot logging
- **GIVEN** a screenshot is requested
- **WHEN** the screenshot is captured
- **THEN** it SHALL log:
  - `span: "page.screenshot"`
  - `path`: Output file path
  - `size`: File size in bytes

#### Scenario: Content extraction logging
- **GIVEN** page content extraction is requested
- **WHEN** extraction completes
- **THEN** it SHALL log:
  - `span: "page.extract"`
  - `url`: Source URL
  - `textLength`: Extracted text length

