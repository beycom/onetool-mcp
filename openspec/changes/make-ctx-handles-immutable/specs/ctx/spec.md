## MODIFIED Requirements

### Requirement: Write Content to Context Store

The `ctx.write()` function SHALL store content synchronously, detect its format,
normalise it, generate a TOC, and return a compact immutable handle dict
immediately. A handle SHALL become visible only when its complete content and
metadata record has been atomically published.

#### Scenario: Basic write returns immediately
- **WHEN** `ctx.write("some content")` is called
- **THEN** it SHALL return a dict containing `handle`, `source`, `size_bytes`,
  `total_lines`, `format`, and `status`
- **AND** `status` SHALL be `"ready"` immediately (write is synchronous)
- **AND** `handle` SHALL be a 32-character opaque hexadecimal string
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
- **WHEN** `ctx.write(content, source="webfetch:docs.test")` is called
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
  `ctx.query`, `ctx.inspect`, `ctx.delete`) is called with a handle dict (e.g.
  `{"handle": "b2d18a1b9f9e4c86a3fbeb9ba2685107", ...}`) in place of a
  string handle
- **THEN** the tool SHALL transparently extract the `"handle"` key and proceed
  as if the string ID was passed directly
- **WHEN** a non-string, non-handle-dict value is passed as `handle`
- **THEN** the tool SHALL return `{"error": "handle must be a string ... use h['handle']"}`
  without raising an exception or leaking an OS error

#### Scenario: Atomic immutable publication
- **GIVEN** a new handle record is being created
- **WHEN** a reader checks the handle before, during, or after publication
- **THEN** the reader SHALL observe either handle-not-found or the complete
  immutable content and metadata record
- **AND** no subsequent operation SHALL update that handle

#### Scenario: Creation failure
- **GIVEN** content serialization, content writing, metadata writing, or record
  publication fails
- **WHEN** `ctx.write` attempts to create the handle
- **THEN** no handle SHALL become visible
- **AND** no staging record SHALL remain

#### Scenario: Concurrent handle collision
- **GIVEN** independent writers generate the same candidate handle
- **WHEN** they publish concurrently
- **THEN** one writer SHALL publish that handle exclusively
- **AND** every other writer SHALL retry with a new handle without replacing it

### Requirement: Read Raw Content

The `ctx.read()` function SHALL return paginated raw content with long lines
truncated and SHALL NOT mutate the stored record.

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
- **THEN** it SHALL return handle metadata: source, format, size_bytes,
  total_lines, status, and created_at

#### Scenario: Repeated reads are immutable
- **GIVEN** a stored handle
- **WHEN** it is read repeatedly in raw, TOC, or metadata mode
- **THEN** its stored bytes and modification times SHALL remain unchanged

#### Scenario: Unknown handle
- **WHEN** `ctx.read("badhandle")` is called
- **THEN** it SHALL return an error message indicating handle not found

#### Scenario: Expired handle
- **GIVEN** a handle that has exceeded TTL
- **WHEN** `ctx.read(h)` is called
- **THEN** it SHALL return an error message indicating the handle has expired

### Requirement: Inspect Handle

The `ctx.inspect()` function SHALL return detailed immutable metadata for a
single handle.

#### Scenario: Inspect ready handle
- **GIVEN** a ready handle
- **WHEN** `ctx.inspect(h)` is called
- **THEN** it SHALL return: handle, source, format, size_bytes, total_lines,
  status, created_at, toc_entries, and ttl_remaining

#### Scenario: Inspect unknown handle
- **WHEN** `ctx.inspect("badhandle")` is called
- **THEN** it SHALL return an error message indicating handle not found

### Requirement: Delete Handle

The `ctx.delete()` function SHALL remove a single immutable handle record and
all of its data.

#### Scenario: Delete a handle
- **GIVEN** a stored handle `h`
- **WHEN** `ctx.delete(h)` is called
- **THEN** it SHALL remove the complete handle directory
- **AND** subsequent `ctx.read(h)` SHALL return handle not found
- **AND** it SHALL return `{"deleted": h}`

#### Scenario: Delete unknown handle
- **WHEN** `ctx.delete("badhandle")` is called
- **THEN** it SHALL return `{"error": "Handle not found: badhandle"}`

#### Scenario: Delete races a read
- **GIVEN** deletion and a read overlap
- **WHEN** the record is removed
- **THEN** the read MAY return handle-not-found
- **AND** it SHALL NOT observe a partial replacement record

## REMOVED Requirements

### Requirement: Append Content

**Reason**: Appending mutates a session handle through an unsafe read-modify-write
cycle and has no production consumer.

**Migration**: Create a new handle containing the desired complete content.
