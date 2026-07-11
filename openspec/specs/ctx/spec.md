# ctx Specification

## Purpose

Defines the `ctx` pack providing a smart-context store backed by flat files. The pack enables agents to store, navigate, and query large content blobs without filling the context window. Content is stored with a TTL, format-detected on write, and accessible through a set of focused read/search/navigation/query tools.

## Requirements

### Requirement: Write Content to Context Store

The `ctx.write()` function SHALL store content synchronously, detect its format,
normalise it, generate a TOC, and return a compact handle dict immediately.

#### Scenario: Basic write returns immediately
- **WHEN** `ctx.write("some content")` is called
- **THEN** it SHALL return a dict containing `handle`, `source`, `size_bytes`,
  `total_lines`, `format`, and `status`
- **AND** `status` SHALL be `"ready"` immediately (write is synchronous)
- **AND** `handle` SHALL be a short opaque string (8 hex chars)
- **AND** `format` SHALL be one of `"json"`, `"yaml"`, `"markdown"`, `"text"`

#### Scenario: Write detects JSON and pretty-prints
- **WHEN** `ctx.write(content)` is called where `content` is a single-line JSON blob
- **THEN** the stored content SHALL be pretty-printed (`indent=2`)
- **AND** `total_lines` in the response SHALL reflect the pretty-printed line count
- **AND** `format` SHALL be `"json"`

#### Scenario: Write detects YAML
- **WHEN** `ctx.write(content)` is called where content parses as a YAML mapping or
  sequence
- **THEN** `format` SHALL be `"yaml"`
- **AND** content SHALL be stored as-is (no transformation)

#### Scenario: Write detects Markdown
- **WHEN** `ctx.write(content)` is called where content contains `#` heading lines
  in the first 50 lines
- **THEN** `format` SHALL be `"markdown"`
- **AND** content SHALL be stored as-is

#### Scenario: Write defaults to text
- **WHEN** content does not match JSON, YAML, or Markdown patterns
- **THEN** `format` SHALL be `"text"`

#### Scenario: Write with source label
- **WHEN** `ctx.write(content, source="webfetch:docs.example.com")` is called
- **THEN** `source` SHALL appear in the returned dict and be retrievable via `ctx.list`

#### Scenario: Verbose mode
- **WHEN** `ctx.write(content, verbose=True)` is called
- **THEN** the response SHALL additionally include `preview` (first 5 non-empty lines)
- **WHEN** `ctx.write(content)` is called (default `verbose=False`)
- **THEN** `preview` SHALL NOT be present in the response

#### Scenario: Handle-dict dereference (write)
- **WHEN** `ctx.write(content)` is called where `content` is a dict containing a
  `"handle"` key
- **THEN** `ctx.write` SHALL transparently dereference the handle, read its content,
  and store it under a new handle
- **AND** if the referenced handle is not found it SHALL return `{"error": ...}`

#### Scenario: Handle-dict passed as `handle` argument (read-side tools)
- **WHEN** any read-side tool (`ctx.read`, `ctx.toc`, `ctx.grep`, `ctx.slice`,
  `ctx.query`, `ctx.append`, `ctx.inspect`, `ctx.delete`) is called with a handle
  dict (e.g. `{"handle": "b2d18a1b", ...}`) in place of a string handle
- **THEN** the tool SHALL transparently extract the `"handle"` key and proceed
  as if the string ID was passed directly
- **WHEN** a non-string, non-handle-dict value is passed as `handle`
- **THEN** the tool SHALL return `{"error": "handle must be a string ... use h['handle']"}`
  without raising an exception or leaking an OS error

---

### Requirement: Read Raw Content

The `ctx.read()` function SHALL return paginated raw content with long lines truncated.

#### Scenario: Basic read with defaults
- **GIVEN** a stored handle `h`
- **WHEN** `ctx.read(h)` is called
- **THEN** it SHALL return lines 1–100 (default offset=1, limit=100)
- **AND** response SHALL include `handle`, `content`, `total_lines`, `returned`,
  `offset`, `has_more`, `progress`, `total_size_bytes`
- **AND** `content` SHALL be a single string with embedded newlines (not a list)

#### Scenario: Long lines are truncated
- **GIVEN** a handle whose content contains a line exceeding 500 characters
- **WHEN** `ctx.read(h)` is called
- **THEN** that line SHALL be truncated to 500 chars with a `[+N chars]` suffix
  where N is the number of omitted characters

#### Scenario: Read with offset and limit
- **GIVEN** a handle with 500 lines
- **WHEN** `ctx.read(h, offset=101, limit=50)` is called
- **THEN** it SHALL return lines 101–150

#### Scenario: Read with tail
- **WHEN** `ctx.read(h, tail=20)` is called
- **THEN** it SHALL return the last 20 lines

#### Scenario: Read mode toc
- **WHEN** `ctx.read(h, mode="toc")` is called
- **THEN** it SHALL return output equivalent to `ctx.toc(h)`

#### Scenario: Read mode meta
- **WHEN** `ctx.read(h, mode="meta")` is called
- **THEN** it SHALL return handle metadata: source, format, size_bytes, total_lines,
  status, created_at, access_count

#### Scenario: Unknown handle
- **WHEN** `ctx.read("badhandle")` is called
- **THEN** it SHALL return an error message indicating handle not found

#### Scenario: Expired handle
- **GIVEN** a handle that has exceeded TTL
- **WHEN** `ctx.read(h)` is called
- **THEN** it SHALL return an error message indicating the handle has expired

---

### Requirement: Regex Line Search

The `ctx.grep()` function SHALL perform regex line search with optional context lines
and long-line truncation.

#### Scenario: Basic grep
- **GIVEN** a handle with lines containing "error" and lines without
- **WHEN** `ctx.grep(h, pattern="error")` is called
- **THEN** it SHALL return only lines matching the regex pattern

#### Scenario: Long lines are truncated
- **GIVEN** a handle whose content contains a matching line exceeding 500 characters
- **WHEN** `ctx.grep(h, pattern="...")` is called and that line matches
- **THEN** the matched line in the result SHALL be truncated to 500 chars with a
  `[+N chars]` suffix

#### Scenario: Grep with context lines
- **WHEN** `ctx.grep(h, pattern="TARGET", context=2)` is called
- **THEN** it SHALL return matching lines plus 2 lines before and after each match
- **AND** non-contiguous groups SHALL be separated by `---`

#### Scenario: Result cap and case sensitivity
- **WHEN** `ctx.grep(h, pattern=...)` matches more than `limit` lines (default 500)
- **THEN** it SHALL return only the first `limit` lines and set `"truncated": true`
- **AND** matching SHALL be case-insensitive by default, with `ignore_case=False` enabling case-sensitive search

---

### Requirement: Section Slicing

The `ctx.slice()` function SHALL extract content by section number, heading name,
or line range, with format-aware dispatch.

#### Scenario: Slice by line range (any format)
- **WHEN** `ctx.slice(h, select="50:100")` is called
- **THEN** it SHALL return lines 50–100 inclusive (1-indexed)

#### Scenario: Slice by section number (markdown)
- **GIVEN** a markdown handle with a TOC
- **WHEN** `ctx.slice(h, select="#3")` is called
- **THEN** it SHALL return the content of the third section (from TOC line to next
  same-or-higher-level heading)

#### Scenario: Slice by integer section number (markdown)
- **GIVEN** a markdown handle with a TOC
- **WHEN** `ctx.slice(h, select=3)` is called with an integer
- **THEN** it SHALL treat the integer as equivalent to `"#3"` and return the third section

#### Scenario: Slice by heading name (markdown)
- **GIVEN** a markdown handle
- **WHEN** `ctx.slice(h, select="Prerequisites")` is called
- **THEN** it SHALL return the section whose heading contains "Prerequisites"
  (case-insensitive substring match)

#### Scenario: jmespath-like select on json/yaml redirects to query
- **WHEN** `ctx.slice(h, select=".spec.containers")` is called on a `json` or `yaml`
  handle
- **THEN** it SHALL return a clear error directing the caller to use `ctx.query()`
  instead

#### Scenario: Section not found
- **WHEN** `ctx.slice(h, select="NonExistentSection")` is called
- **THEN** it SHALL return an error message indicating section not found

---

### Requirement: Table of Contents

The `ctx.toc()` function SHALL return a format-aware table of contents read from
stored metadata — no content re-parse needed.

#### Scenario: TOC for markdown content
- **GIVEN** a markdown handle
- **WHEN** `ctx.toc(h)` is called
- **THEN** it SHALL return a numbered list of sections with heading level, title, and
  line number
- **AND** the data SHALL be read from the stored metadata (no content file parse)

#### Scenario: TOC for JSON content
- **GIVEN** a json handle whose top level is a dict
- **WHEN** `ctx.toc(h)` is called
- **THEN** it SHALL return a list of top-level keys with type and size hints
  (e.g. `dependencies (dict, 45 keys)`, `name (str)`)

#### Scenario: TOC for JSON array
- **GIVEN** a json handle whose top level is a list
- **WHEN** `ctx.toc(h)` is called
- **THEN** it SHALL return a single summary entry: `[array] (list, N items)`

#### Scenario: TOC for YAML content
- **GIVEN** a yaml handle
- **WHEN** `ctx.toc(h)` is called
- **THEN** it SHALL return top-level keys with type and size hints, same as JSON

#### Scenario: TOC for text content
- **GIVEN** a text handle
- **WHEN** `ctx.toc(h)` is called
- **THEN** it SHALL return an empty list with a note that text format has no structure

---

### Requirement: Structured Data Query

The `ctx.query()` function SHALL evaluate a jmespath expression against the parsed
content of a `json` or `yaml` handle and return the matched value.

#### Scenario: Query a JSON handle
- **GIVEN** a json handle containing `{"name": "myapp", "version": "1.0.0"}`
- **WHEN** `ctx.query(h, expr="name")` is called
- **THEN** it SHALL return `{"handle": h, "expr": "name", "result": "myapp"}`

#### Scenario: Query nested path
- **GIVEN** a json handle with nested structure
- **WHEN** `ctx.query(h, expr="spec.containers[0].image")` is called
- **THEN** it SHALL return the matched value as the `result` field

#### Scenario: Query with filter expression
- **GIVEN** a json handle containing a list of objects with a `status` field
- **WHEN** `ctx.query(h, expr="items[?status == 'active'].name")` is called
- **THEN** it SHALL return the list of matching names as `result`

#### Scenario: dict or list result is pretty-printed
- **WHEN** the jmespath result is a dict or list
- **THEN** `result` SHALL be a JSON-formatted string (`indent=2`)

#### Scenario: No match returns error with hint
- **WHEN** `ctx.query(h, expr="nonexistent.path")` is called and no match is found
- **THEN** it SHALL return `{"error": "No match", "expr": "...", "hint": "Use ctx.toc('<handle>') to see available keys"}`

#### Scenario: Query on wrong format returns clear error
- **WHEN** `ctx.query(h, expr="...")` is called on a `markdown` or `text` handle
- **THEN** it SHALL return an error explaining that `ctx.query()` requires `json` or
  `yaml` format and directing the caller to `ctx.slice()` or `ctx.grep()`

#### Scenario: Query on unknown handle
- **WHEN** `ctx.query("badhandle", expr="...")` is called
- **THEN** it SHALL return an error message indicating handle not found

#### Scenario: Invalid jmespath expression
- **WHEN** `ctx.query(h, expr="[invalid syntax")` is called
- **THEN** it SHALL return an error message describing the jmespath parse failure

#### Scenario: Query YAML handle
- **GIVEN** a yaml handle
- **WHEN** `ctx.query(h, expr="metadata.name")` is called
- **THEN** it SHALL parse the YAML and evaluate the expression identically to a JSON handle

---

### Requirement: Multi-question LLM Query

The `ctx.ask()` function SHALL accept one or more questions about stored content, send them to the configured LLM service in a single call, and return structured question/answer pairs — mirroring the `img.ask` interface for text content.

#### Scenario: Single question string

- **WHEN** `ctx.ask(h, q="What is the recommended entry point?")` is called
- **THEN** it SHALL return `{"handle": h, "result": [{"question": "What is the recommended entry point?", "answer": "<answer>"}]}`

#### Scenario: Batch questions list

- **WHEN** `ctx.ask(h, q=["What is the recommended entry point?", "What are common mistakes?"])` is called
- **THEN** it SHALL send both questions in a single LLM service call
- **AND** return `{"handle": h, "result": [{"question": "...", "answer": "..."}, {"question": "...", "answer": "..."}]}`
- **AND** the order of results SHALL match the order of questions provided

#### Scenario: Model override

- **WHEN** `ctx.ask(h, q="...", model="haiku")` is called
- **THEN** it SHALL pass the specified model to the LLM service
- **AND** fall back to the LLM service configured default if `model=None`

#### Scenario: LLM service not configured

- **WHEN** `ctx.ask(h, q="...")` is called and no LLM service is configured
- **THEN** it SHALL return `{"handle": h, "error": "<message explaining an LLM service must be configured>"}`
- **AND** it SHALL NOT raise an unhandled exception

#### Scenario: Unknown handle

- **WHEN** `ctx.ask("badhandle", q="...")` is called
- **THEN** it SHALL return `{"handle": "badhandle", "error": "Handle not found: badhandle"}`

#### Scenario: Large content truncation

- **GIVEN** a handle whose total content exceeds `ask_max_bytes`
- **WHEN** `ctx.ask(h, q="...")` is called
- **THEN** it SHALL send the first `ask_max_bytes` bytes of content to the model
- **AND** the response SHALL include a `truncated: true` field
- **AND** the response MAY include a `hint` suggesting `ctx.slice` to narrow scope before re-querying

---

### Requirement: Append Content

The `ctx.append()` function SHALL add content to an existing handle, re-detect
format on the combined content, regenerate the TOC, and update metadata.

#### Scenario: Basic append
- **GIVEN** a ready handle `h`
- **WHEN** `ctx.append(h, "additional content")` is called
- **THEN** the combined content SHALL be available via `ctx.read`
- **AND** format SHALL be re-detected on the combined content
- **AND** TOC SHALL be regenerated from the combined content
- **AND** `status` SHALL remain `"ready"` on success

#### Scenario: Append to unknown handle
- **WHEN** `ctx.append("badhandle", "content")` is called
- **THEN** it SHALL return an error message indicating handle not found

---

### Requirement: List Active Handles

The `ctx.list()` function SHALL return all active (non-expired) handles with summary information.

#### Scenario: List all handles
- **WHEN** `ctx.list()` is called
- **THEN** it SHALL return a table of handles: handle, source, size, status, TTL remaining
- **AND** expired handles SHALL NOT appear

#### Scenario: Filter by source
- **WHEN** `ctx.list(source="webfetch")` is called
- **THEN** it SHALL return only handles whose source matches the pattern (substring)

#### Scenario: Filter by status
- **WHEN** `ctx.list(status="failed")` is called
- **THEN** it SHALL return only handles with that status

#### Scenario: Invalid status value
- **WHEN** `ctx.list(status="invalid_value")` is called
- **THEN** it SHALL raise `ValueError` immediately with a message listing valid values
- **AND** it SHALL NOT return a filtered (possibly empty) result silently

#### Scenario: Empty store
- **WHEN** no handles are active
- **THEN** `ctx.list()` SHALL return an empty list `[]`

---

### Requirement: Inspect Handle

The `ctx.inspect()` function SHALL return detailed metadata for a single handle.

#### Scenario: Inspect ready handle
- **GIVEN** a ready handle
- **WHEN** `ctx.inspect(h)` is called
- **THEN** it SHALL return: handle, source, format, size_bytes, total_lines, status,
  toc_entries, ttl_remaining, access_count

#### Scenario: Inspect unknown handle
- **WHEN** `ctx.inspect("badhandle")` is called
- **THEN** it SHALL return an error message indicating handle not found

---

### Requirement: Session Statistics

The `ctx.stats()` function SHALL return session-level storage metrics.

#### Scenario: Stats output
- **WHEN** `ctx.stats()` is called
- **THEN** it SHALL return: total_handles, handles_by_status (dict),
  total_bytes_stored, estimated_tokens_saved
- **AND** it SHALL NOT include `db_size_bytes` (no database)

---

### Requirement: Delete Handle

The `ctx.delete()` function SHALL remove a single handle and all associated data.

#### Scenario: Delete a handle
- **GIVEN** a stored handle `h`
- **WHEN** `ctx.delete(h)` is called
- **THEN** it SHALL remove the handle and its backing content file
- **AND** subsequent `ctx.read(h)` SHALL return handle not found
- **AND** it SHALL return `{"deleted": h}`

#### Scenario: Delete unknown handle
- **WHEN** `ctx.delete("badhandle")` is called
- **THEN** it SHALL return `{"error": "Handle not found: badhandle"}`

---

### Requirement: Bulk Purge

The `ctx.purge()` function SHALL bulk-delete handles matching age, source, or status criteria.

#### Scenario: Default purge (expired handles only)
- **WHEN** `ctx.purge()` is called with no arguments
- **THEN** it SHALL delete only handles that have passed their TTL (`expires_at`), so routine cleanup never removes handles still within their advertised lifetime
- **AND** return `{"deleted": N, "bytes_freed": N}` where `bytes_freed` is the sum of `size_bytes` of deleted handles

#### Scenario: Purge by age
- **WHEN** `ctx.purge(minutes=60)` is called
- **THEN** it SHALL delete all handles created more than 60 minutes ago
- **AND** return a count of deleted handles

#### Scenario: Purge by source pattern
- **WHEN** `ctx.purge(source="webfetch")` is called
- **THEN** it SHALL delete all handles whose source matches "webfetch" AND are past their TTL (default age filter)

#### Scenario: Purge by status
- **WHEN** `ctx.purge(status="failed")` is called
- **THEN** it SHALL delete all handles with `status="failed"` AND past their TTL (default age filter)

#### Scenario: Purge all (no filters)
- **WHEN** `ctx.purge(delete_all=True)` is called with no source or status filters
- **THEN** it SHALL delete every handle regardless of age
- **AND** return `{"deleted": N, "bytes_freed": N}`

#### Scenario: Purge all with source filter
- **WHEN** `ctx.purge(delete_all=True, source="brave")` is called
- **THEN** it SHALL delete all handles whose source matches "brave" regardless of age
- **AND** handles from other sources SHALL NOT be deleted

#### Scenario: Purge all with status filter
- **WHEN** `ctx.purge(delete_all=True, status="failed")` is called
- **THEN** it SHALL delete all handles with `status="failed"` regardless of age
- **AND** handles with other statuses SHALL NOT be deleted

#### Scenario: Purge with no matches
- **WHEN** no handles match the purge criteria
- **THEN** it SHALL return `{"deleted": 0, "bytes_freed": 0}`

#### Scenario: Zero or negative minutes raises
- **WHEN** `ctx.purge(minutes=0)` or `ctx.purge(minutes=-1)` is called
- **THEN** it SHALL raise `ValueError` with message containing "positive"

---

### Requirement: Configuration

The `ctx` pack SHALL support optional configuration via `onetool.yaml`.

#### Scenario: Default configuration
- **GIVEN** no `tools.ctx` block in `onetool.yaml`
- **WHEN** the ctx pack is used
- **THEN** TTL SHALL default to 3600 seconds (1 hour)
- **AND** `max_line_chars` SHALL default to 500
- **AND** `ask_max_bytes` SHALL default to 204800 (200KB)

#### Scenario: Custom TTL
- **GIVEN** `tools.ctx.ttl: 7200` in config
- **WHEN** a handle is written
- **THEN** its TTL SHALL be 7200 seconds

#### Scenario: Custom max_line_chars
- **GIVEN** `tools.ctx.max_line_chars: 200` in config
- **WHEN** `ctx.read()` or `ctx.grep()` returns a long line
- **THEN** lines SHALL be truncated at 200 characters
