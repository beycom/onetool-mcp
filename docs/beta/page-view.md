# Page View

Tools for analyzing browse session captures from `ot-browse`.

| Function | Description |
|----------|-------------|
| `page.list(...)` | List available sessions |
| `page.captures(session_id, ...)` | List captures in a session |
| `page.annotations(session_id, capture_id, ...)` | Get annotations with selectors and HTML |
| `page.context(session_id, capture_id, annotation_id, ...)` | Get HTML/accessibility context for annotation |
| `page.search(session_id, capture_id, pattern, ...)` | Search HTML and accessibility tree |
| `page.accessibility(session_id, capture_id, filter_type, ...)` | Filter large accessibility tree |
| `page.diff(session_id, capture_id_1, capture_id_2, ...)` | Compare two captures |
| `page.summary(session_id, capture_id, ...)` | Quick overview of a capture |

**Key Parameters:**
- `session_id`: The session directory name (e.g., "2025-12-31_22-46_session_001")
- `capture_id`: The capture directory name (e.g., "capture_001")
- `sessions_dir`: Path to sessions directory (default: `.browse/`)
- `filter_type`: For accessibility - "interactive", "headings", "forms", "links", "landmarks"

**Data Location:** `.browse/{session}/{capture}/`

**Implementation notes:**
- Streams large files (HTML, accessibility tree) instead of loading into memory
- Batch line number lookups for performance on 8K+ line HTML files
- Filters 258KB accessibility trees down to <10KB

**Comparison:** Original implementation; works with `ot-browse` captures.

**License:** MIT
