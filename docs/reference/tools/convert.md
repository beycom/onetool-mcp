# Convert

**Transform documents to LLM-friendly Markdown.**

Convert PDF, Word, PowerPoint, and Excel documents to Markdown with LLM-optimised output. Each conversion produces two files: a pure content file with exact line numbers, and a separate TOC file with frontmatter and navigation.

## Highlights

- Two-file output: pure content + separate TOC with line numbers
- Parallel batch processing with glob patterns
- Diff-stable image naming using content hashes
- Format-specific features (PDF bookmarks, speaker notes, formulas)

## Functions

| Function | Description |
|----------|-------------|
| `convert.pdf(pattern, output_dir)` | Convert PDF documents to Markdown |
| `convert.word(pattern, output_dir)` | Convert Word documents (.docx) to Markdown |
| `convert.powerpoint(pattern, output_dir, include_notes)` | Convert PowerPoint presentations (.pptx) to Markdown |
| `convert.excel(pattern, output_dir, include_formulas)` | Convert Excel spreadsheets (.xlsx) to Markdown |
| `convert.auto(pattern, output_dir)` | Auto-detect format and convert |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `pattern` | str | Glob pattern for input files (e.g., `docs/*.pdf`, `**/*.docx`) |
| `output_dir` | str | Directory for output Markdown files and images |
| `include_notes` | bool | Include speaker notes in PowerPoint conversion |
| `include_formulas` | bool | Include cell formulas in Excel conversion |

## Output Format

Each conversion produces two files:

### Main Content File (`{name}.md`)

Pure content starting at line 1 - no frontmatter or TOC. This ensures line numbers in the TOC are exact.

### TOC File (`{name}.toc.md`)

A separate file with frontmatter and table of contents:

```markdown
---
source: path/to/document.pdf
converted: 2026-01-20T10:30:00Z
pages: 15
checksum: sha256:abc123...
---

# Table of Contents

**Document:** [document.md](document.md)

## How to Use This TOC

Each entry shows `(lines <start>-<end>)` for the main document.
To read a section efficiently:

1. Find the section you need below
2. Use the line range to read only that portion of [document.md](document.md)
3. Line numbers are exact - no offset needed

---

## Contents

- [Introduction](document.md#introduction) (lines 1-50)
  - [Background](document.md#background) (lines 15-30)
- [Results](document.md#results) (lines 51-100)
```

### Diff-Stable Images

Images are named using content hashes (`img_abc123.png`) for stable diffs across regenerations.

## Examples

### Converting PDFs

```python
# Single file
convert.pdf(pattern="report.pdf", output_dir="output")

# Batch conversion with glob
convert.pdf(pattern="docs/**/*.pdf", output_dir="converted")
```

### Converting Word Documents

```python
# Single document
convert.word(pattern="spec.docx", output_dir="output")

# All Word docs in folder
convert.word(pattern="documents/*.docx", output_dir="md")
```

### Converting PowerPoint

```python
# Basic conversion
convert.powerpoint(pattern="deck.pptx", output_dir="output")

# Include speaker notes
convert.powerpoint(
    pattern="presentations/*.pptx",
    output_dir="output",
    include_notes=True
)
```

### Converting Excel

```python
# Basic conversion (values only)
convert.excel(pattern="data.xlsx", output_dir="output")

# Include formulas
convert.excel(
    pattern="spreadsheets/*.xlsx",
    output_dir="output",
    include_formulas=True
)
```

### Auto-Detection

```python
# Convert all supported formats
convert.auto(pattern="documents/*", output_dir="converted")

# Recursive with mixed formats
convert.auto(pattern="input/**/*", output_dir="output")
```

## Supported Formats

| Format     | Extension | Converter    | Install                 |
|------------|-----------|--------------|-------------------------|
| PDF        | `.pdf`    | PyMuPDF      | included                |
| Word       | `.docx`   | python-docx  | included                |
| PowerPoint | `.pptx`   | python-pptx  | included                |
| Excel      | `.xlsx`   | openpyxl     | `pip install openpyxl`  |

Excel conversion requires the `openpyxl` package. Install it before using `convert.excel()`.

## Features by Format

### PDF
- Lazy page loading for memory efficiency
- Outline-based heading extraction (uses PDF bookmarks)
- Falls back to "Page N" headers if no outline
- Image extraction with soft-mask transparency support

### Word
- Heading style detection (Heading 1-6)
- Table conversion to Markdown
- Inline image extraction
- Bold, italic, underline formatting

### PowerPoint
- Slide titles as H2 headers
- Bullet point detection
- Table conversion
- Image extraction
- Optional speaker notes

### Excel
- Sheet-based sections
- Streaming for large files
- Markdown table formatting
- Optional formula extraction

## Batch Processing

All converters support glob patterns and process multiple files in parallel:

```python
# Process all PDFs in parallel
convert.pdf(pattern="archive/**/*.pdf", output_dir="output")
# Converted 25 files, 0 failed
# Outputs:
#   output/report1.md + output/report1.toc.md
#   output/report2.md + output/report2.toc.md
#   ...
```

## Source

[PyMuPDF](https://pymupdf.readthedocs.io/) | [python-docx](https://python-docx.readthedocs.io/) | [python-pptx](https://python-pptx.readthedocs.io/) | [openpyxl](https://openpyxl.readthedocs.io/)
