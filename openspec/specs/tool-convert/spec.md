# tool-convert Specification

## Purpose

Convert PDF, Word, PowerPoint, and Excel documents to LLM-friendly Markdown with YAML frontmatter, table of contents, and diff-stable output.
## Requirements
### Requirement: Glob Pattern Input

The convert tool SHALL accept glob patterns for file selection.

#### Scenario: Single file conversion
- **GIVEN** a single file path `docs/report.pdf`
- **WHEN** `convert.pdf(pattern="docs/report.pdf", output_dir="docs/md")` is called
- **THEN** it SHALL convert that single file

#### Scenario: Glob pattern conversion
- **GIVEN** multiple PDF files matching `input/*.pdf`
- **WHEN** `convert.pdf(pattern="input/*.pdf", output_dir="docs/md")` is called
- **THEN** it SHALL convert all matching files in parallel

#### Scenario: Recursive glob
- **GIVEN** files in nested directories
- **WHEN** `convert.auto(pattern="docs/**/*.docx", output_dir="output")` is called
- **THEN** it SHALL match files recursively

#### Scenario: Home directory expansion
- **GIVEN** a pattern with tilde `~/documents/*.pdf`
- **WHEN** the pattern is processed
- **THEN** `~` SHALL expand to the user's home directory

#### Scenario: No matches
- **GIVEN** a glob pattern matching no files
- **WHEN** the converter is called
- **THEN** it SHALL return `"No files matched pattern: {pattern}"`

---

### Requirement: Relative Path Resolution

All paths SHALL be relative to the project directory.

#### Scenario: Input path resolution
- **GIVEN** a pattern `docs/*.pdf`
- **WHEN** the tool resolves the path
- **THEN** it SHALL resolve relative to the project working directory

#### Scenario: Output path resolution
- **GIVEN** an output_dir `converted/md`
- **WHEN** files are written
- **THEN** they SHALL be written relative to the project working directory

#### Scenario: Absolute paths
- **GIVEN** an absolute path `/tmp/docs/*.pdf`
- **WHEN** the pattern is processed
- **THEN** it SHALL be used as-is without modification

---

### Requirement: Async Execution

All conversions SHALL execute asynchronously.

#### Scenario: Parallel file processing
- **GIVEN** a glob matching multiple files
- **WHEN** conversion starts
- **THEN** files SHALL be processed in parallel using async

#### Scenario: Completion summary
- **GIVEN** a batch conversion completes
- **WHEN** all files are processed
- **THEN** it SHALL return a summary with:
  - Total files converted
  - Total files failed
  - Total files skipped (for `auto()` only - unsupported formats)
  - List of output paths
  - List of errors (if any)

---

### Requirement: PDF Conversion

The `convert.pdf()` function SHALL convert PDF documents to markdown.

#### Scenario: Basic PDF conversion
- **GIVEN** a valid PDF file
- **WHEN** `convert.pdf(pattern="file.pdf", output_dir="output")` is called
- **THEN** it SHALL write `output/file.md` with page-by-page text
- **AND** embedded images SHALL be extracted to `output/file_images/`
- **AND** image references SHALL be included as markdown links

#### Scenario: PDF with soft-mask images
- **GIVEN** a PDF with transparency (soft-mask images)
- **WHEN** the PDF is converted
- **THEN** images SHALL preserve transparency as RGBA PNG

---

### Requirement: Word Document Conversion

The `convert.word()` function SHALL convert DOCX documents to markdown.

#### Scenario: Basic Word conversion
- **GIVEN** a valid DOCX file
- **WHEN** `convert.word(pattern="file.docx", output_dir="output")` is called
- **THEN** it SHALL write `output/file.md` with:
  - Headings mapped to H1-H6
  - Bold/italic formatting preserved
  - Tables converted to markdown tables
  - Inline images extracted to `output/file_images/`

---

### Requirement: PowerPoint Conversion

The `convert.powerpoint()` function SHALL convert PPTX presentations to markdown.

#### Scenario: Basic PowerPoint conversion
- **GIVEN** a valid PPTX file
- **WHEN** `convert.powerpoint(pattern="file.pptx", output_dir="output")` is called
- **THEN** it SHALL write `output/file.md` with:
  - Slide-by-slide structure (## Slide N headers)
  - Title extraction
  - Bullet points as markdown lists
  - Tables and images extracted

#### Scenario: Speaker notes
- **GIVEN** a presentation with speaker notes
- **WHEN** `include_notes=True` is specified
- **THEN** speaker notes SHALL be included after slide content

---

### Requirement: Excel Conversion

The `convert.excel()` function SHALL convert XLSX spreadsheets to markdown.

#### Scenario: Basic Excel conversion
- **GIVEN** a valid XLSX file
- **WHEN** `convert.excel(pattern="file.xlsx", output_dir="output")` is called
- **THEN** it SHALL write `output/file.md` with markdown tables for each sheet

#### Scenario: Multi-sheet workbook
- **GIVEN** an Excel file with multiple sheets
- **WHEN** converted to markdown
- **THEN** each sheet SHALL be a separate section (## Sheet: {name})

#### Scenario: Formula extraction
- **GIVEN** an Excel file with formulas
- **WHEN** `include_formulas=True` is specified
- **THEN** cell formulas SHALL be included as comments

---

### Requirement: Auto-Detection

The `convert.auto()` function SHALL detect file format and use the appropriate converter.

#### Scenario: Format detection
- **GIVEN** files with extensions `.pdf`, `.docx`, `.pptx`, or `.xlsx`
- **WHEN** `convert.auto(pattern="docs/*", output_dir="output")` is called
- **THEN** it SHALL use the corresponding converter for each file

#### Scenario: Mixed formats
- **GIVEN** a glob matching multiple file types
- **WHEN** `convert.auto()` is called
- **THEN** each file SHALL be converted with its appropriate converter

#### Scenario: Unsupported format
- **GIVEN** a file with unsupported extension
- **WHEN** `convert.auto()` processes it
- **THEN** it SHALL skip the file
- **AND** include it in the skipped count (separate from errors)

---

### Requirement: Frontmatter Metadata

All converted documents SHALL include YAML frontmatter.

#### Scenario: Frontmatter content
- **GIVEN** a document is converted
- **WHEN** the markdown file is written
- **THEN** it SHALL begin with YAML frontmatter containing:
  - `source`: relative path to original file
  - `converted`: ISO 8601 timestamp (source file mtime for diff-stability)
  - `pages`: page/slide/sheet count
  - `checksum`: SHA256 hash of source file

#### Scenario: Frontmatter format
- **GIVEN** a converted PDF `docs/report.pdf`
- **WHEN** written to `output/report.md`
- **THEN** the frontmatter SHALL be:

  ```yaml
  ---
  source: docs/report.pdf
  converted: 2026-01-19T10:30:00Z
  pages: 42
  checksum: sha256:abc123...
  ---
  ```

---

### Requirement: Table of Contents with Line Numbers

All converted documents SHALL include a table of contents with line references.

#### Scenario: TOC generation
- **GIVEN** a document with headings
- **WHEN** converted to markdown
- **THEN** a Table of Contents SHALL be generated after the frontmatter

#### Scenario: Line number references
- **GIVEN** a TOC entry for a section
- **WHEN** the TOC is rendered
- **THEN** each entry SHALL include line range in backticks:

  ```markdown
  - [Requirements](#requirements) `L52-L141` (90 lines)
  ```

#### Scenario: Nested headings
- **GIVEN** a document with nested heading levels
- **WHEN** the TOC is generated
- **THEN** it SHALL preserve hierarchy as nested markdown lists

#### Scenario: Heading detection by format
- **GIVEN** different source formats
- **WHEN** headings are detected
- **THEN** detection SHALL use:
  - DOCX: Heading styles (Heading 1-6)
  - PPTX: Slide titles
  - XLSX: Sheet names
  - PDF: Built-in outline/bookmarks via `doc.get_toc()`

#### Scenario: PDF with outline
- **GIVEN** a PDF with embedded bookmarks/outline
- **WHEN** the PDF is converted
- **THEN** it SHALL extract outline via `doc.get_toc()` → `[(level, title, page), ...]`
- **AND** insert heading markers at the appropriate positions in content
- **AND** map outline levels to markdown heading levels (H1-H6)

#### Scenario: PDF without outline
- **GIVEN** a PDF without embedded bookmarks
- **WHEN** the PDF is converted
- **THEN** it SHALL use `# Page N` as the only structure
- **AND** the TOC SHALL list pages only

---

### Requirement: Memory-Efficient Processing

All converters SHALL minimise memory usage through streaming or incremental processing.

#### Scenario: PDF streaming
- **GIVEN** any PDF file
- **WHEN** converted
- **THEN** it SHALL use PyMuPDF's lazy page loading
- **AND** process page-by-page without loading all pages into memory
- **AND** write output incrementally

#### Scenario: Excel streaming
- **GIVEN** any Excel file
- **WHEN** converted
- **THEN** it SHALL use openpyxl `read_only=True` mode
- **AND** stream rows without loading entire workbook
- **AND** write output incrementally

#### Scenario: Word incremental processing
- **GIVEN** any Word document
- **WHEN** converted
- **THEN** it SHALL iterate paragraphs/tables sequentially
- **AND** write output incrementally (not buffer all content)
- **NOTE** python-docx loads document structure into memory; incremental output prevents additional memory growth

#### Scenario: PowerPoint incremental processing
- **GIVEN** any PowerPoint file
- **WHEN** converted
- **THEN** it SHALL iterate slides sequentially
- **AND** write output incrementally
- **NOTE** python-pptx loads document structure into memory; incremental output prevents additional memory growth

#### Scenario: Image extraction
- **GIVEN** a document with embedded images
- **WHEN** images are extracted
- **THEN** each image SHALL be written to disk immediately
- **AND** not held in memory after writing

#### Scenario: Progress reporting
- **GIVEN** a conversion in progress
- **WHEN** processing
- **THEN** it SHALL report progress (pages/slides/rows processed)

---

### Requirement: Diff-Stable Output

Converted output SHALL be deterministic for unchanged source files.

#### Scenario: Timestamp stability
- **GIVEN** a source file with unchanged mtime
- **WHEN** converted multiple times
- **THEN** the frontmatter timestamp SHALL be identical

#### Scenario: Image naming stability
- **GIVEN** a document with embedded images
- **WHEN** images are extracted
- **THEN** image filenames SHALL use content hash: `img_{hash8}.png`
- **NOT** sequential numbering

#### Scenario: Whitespace normalisation
- **GIVEN** extracted content
- **WHEN** written to markdown
- **THEN** output SHALL normalise:
  - Line endings to LF
  - Trailing whitespace removed
  - Consistent blank line spacing

---

### Requirement: Output Structure

All converters SHALL write consistent output structure.

#### Scenario: Markdown file naming
- **GIVEN** an input file `report.pdf`
- **WHEN** converted
- **THEN** output SHALL be `{output_dir}/report.md`

#### Scenario: Image directory naming
- **GIVEN** a document with embedded images
- **WHEN** converted
- **THEN** images SHALL be saved to `{output_dir}/{filename}_images/`
- **AND** markdown references SHALL use relative paths

#### Scenario: Directory creation
- **GIVEN** an output_dir that does not exist
- **WHEN** conversion runs
- **THEN** the directory SHALL be created automatically

---

### Requirement: Tool Conventions

The convert tool SHALL follow OneTool tool conventions.

#### Scenario: Follows tool-conventions
- **GIVEN** implementation in `src/ot_tools/convert.py`
- **WHEN** the tool is used
- **THEN** it SHALL follow all requirements in `tool-conventions` spec
- **INCLUDING** keyword-only arguments, LogSpan logging, string error returns

