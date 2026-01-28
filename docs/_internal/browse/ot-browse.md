# ot-browse

Interactive browser debugging TUI for page capture and inspection.

> **Beta Feature**: This CLI is experimental and may change.

## Usage

```bash
ot-browse [URL] [OPTIONS]
```

## Examples

```bash
# Open URL in browser TUI
ot-browse https://example.com

# Open without URL
ot-browse
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Reload page |
| `s` | Capture screenshot |
| `i` | Toggle inspect mode |

## Output

Captures are saved to `.browse/{session}/{capture}/` with:

| File | Contents |
|------|----------|
| `page.html` | Full page HTML |
| `screenshot.webp` | Page screenshot |
| `accessibility.yaml` | ARIA tree |
| `annotations.yaml` | Annotated elements |

## Configuration

| Variable | Description |
|----------|-------------|
| `OT_BROWSE_CONFIG` | Config file path override |

Default config: `config/ot-browse.yaml` or `.onetool/ot-browse.yaml`

## Requirements

```bash
# Install Playwright browser (one-time)
playwright install chromium
```