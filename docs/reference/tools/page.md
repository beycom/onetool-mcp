# page.* Browser Capture Analysis

**Analyze browse session captures from `ot-browse`.**

Tools for inspecting, searching, and comparing browser captures.

## Functions

| Function | Description |
|----------|-------------|
| `page.list()` | List available sessions |
| `page.captures(session_id)` | List captures in a session |
| `page.annotations(session_id, capture_id)` | Get annotations with selectors and HTML |
| `page.context(session_id, capture_id, annotation_id)` | Get HTML/accessibility context for annotation |
| `page.search(session_id, capture_id, pattern)` | Search HTML and accessibility tree |
| `page.accessibility(session_id, capture_id, filter_type)` | Filter large accessibility tree |
| `page.diff(session_id, capture_id_1, capture_id_2)` | Compare two captures |
| `page.summary(session_id, capture_id)` | Quick overview of a capture |

## Parameters

| Parameter | Description |
|-----------|-------------|
| `session_id` | Session directory name (e.g., "2025-12-31_22-46_session_001") |
| `capture_id` | Capture directory name (e.g., "capture_001") |
| `sessions_dir` | Path to sessions directory (default: `.browse/`) |
| `filter_type` | Accessibility filter: "interactive", "headings", "forms", "links", "landmarks" |

## page.list()

List all available browse sessions.

```python
page.list()
page.list(sessions_dir="./my-sessions/")
```

## page.captures()

List captures in a session.

```python
page.captures(session_id="2025-12-31_22-46_session_001")
```

## page.summary()

Get a quick overview of a capture.

```python
page.summary(session_id="session_001", capture_id="capture_001")
```

## page.search()

Search HTML and accessibility tree for patterns.

```python
page.search(session_id="session_001", capture_id="capture_001", pattern="login")
```

## page.accessibility()

Filter large accessibility trees by element type.

```python
page.accessibility(session_id="session_001", capture_id="capture_001", filter_type="interactive")
page.accessibility(session_id="session_001", capture_id="capture_001", filter_type="headings")
```

Filter types: `interactive`, `headings`, `forms`, `links`, `landmarks`

## page.diff()

Compare two captures side by side.

```python
page.diff(session_id="session_001", capture_id_1="capture_001", capture_id_2="capture_002")
```

## Data Location

Captures are stored in `.browse/{session}/{capture}/` with:

- `screenshot.png` - Visual capture
- `page.html` - Full HTML content
- `accessibility.json` - Accessibility tree
- `annotations.json` - User-added annotations

## Performance

- Streams large files instead of loading into memory
- Batch line number lookups for 8K+ line HTML files
- Filters 258KB accessibility trees down to <10KB

## Source

Original implementation for `ot-browse` captures.
