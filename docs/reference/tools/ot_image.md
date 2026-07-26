# OT Image

Load images and ask vision questions through the shared generation route.

Short alias: `img`

## Highlights

- Load images from file paths, URLs, or the clipboard once; reference by handle for follow-up questions
- Ask multiple questions in a single model call — answers returned as paired question/answer list
- Structured summaries (text, mode, type, colours) extracted and cached in `meta.json`
- Clipboard shortcuts `clip_ask()` and `clip_view()` — no handle juggling needed; clipboard is re-read each call and deduplicated when unchanged

## Functions

| Function | Description |
|----------|-------------|
| `ot_image.load(img, ...)` | Load a single image; return a stable handle |
| `ot_image.load_batch(img, ...)` | Load multiple images from a glob or list |
| `ot_image.ask(img, q, ...)` | Ask one or more questions about one or more images (max 8) |
| `ot_image.clip_ask(q, ...)` | Shorthand: ask about the current clipboard image |
| `ot_image.clip_view()` | Shorthand: structured summary of the current clipboard image |
| `ot_image.summary(img)` | Extract and cache a structured summary of an image |
| `ot_image.list()` | List all loaded images with metadata |
| `ot_image.delete(handle)` | Delete an image and free session cache |
| `ot_image.purge(...)` | Delete images by age or delete all |

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `img` | str | Image source: file path, `"https://..."` URL, `"clip"` for clipboard, or `"#handle"` to reference an existing handle |
| `handle` | str | Custom handle name for `load()` (e.g. `"logo"`). Omit for auto-generated `img_<8hex>` |
| `q` | str \| list[str] | Question(s) to ask. Multiple questions are batched into one model call |
| `img` (in `ask()`) | str \| list[str] | Image reference or list of references (max 8) — a list sends all images in one call for comparison questions; response carries `handles` instead of `handle` |
| `max_edge` | int | Max longest edge in pixels for in-memory model resize. Default: `1568` |
| `model` | str \| null | Per-call shortcut or full model id for generation-backed functions |
| `effort` | str \| null | Per-call `low`, `medium`, or `high` effort |
| `all` | bool | `purge(all=True)` deletes all images regardless of age |
| `minutes` | int | `purge(minutes=N)` deletes images older than N minutes. Default: `15` |

## Requires

- An effective generation route whose selected model declares image input support
- The named secret required by that route; CLIProxyAPI routes use the configured
  inference-client secret

## Configuration

### Required

- Generation-backed functions require a complete top-level `llm`, or a complete
  `tools.ot_image.llm`.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.ot_image.llm` | generation selection \| null | `null` | Pack model/effort/timeout/output overrides, or a complete backend switch |
| `tools.ot_image.max_edge` | int | `1568` | Maximum longest edge (pixels) for model-upload resize |
| `tools.ot_image.session_cache_size` | int | `10` | In-memory LRU cache cap (number of images) |

```yaml
llm:
  backend: cliproxy
  interface: responses
  model: luna

tools:
  ot_image:
    llm:
      model: terra
    max_edge: 1568
    session_cache_size: 10
```

### Defaults

- If `tools.ot_image` is omitted, non-generation functions still work.
- Generation selection precedence is call, pack, top-level, then model default.
- A cached `summary()` returns without route or secret resolution; model and effort
  changes do not invalidate it.
- The selected model must advertise image capability and any required structured
  output mode before network I/O.

## Examples

```python
# Load from file and ask a question
result = ot_image.load(img="~/screenshots/dashboard.png")
ot_image.ask(img=result["handle"], q="What is the main metric shown?")

# Ask multiple questions in one call
ot_image.ask(
    img="~/screenshots/dashboard.png",
    q=["What framework is shown?", "Is this dark mode?"]
)

# Load with a custom handle name
ot_image.load(img="~/assets/logo.png", handle="logo")
ot_image.ask(img="#logo", q="What colour is the logo?")

# Compare two images in one call
ot_image.ask(img=["#before", "#after"], q="What differs between image 1 and image 2?")

# Clipboard shortcuts (no load step needed)
ot_image.clip_ask(q="Extract all text from this screenshot")
ot_image.clip_view()

# Structured summary — cached after first call
ot_image.summary(img="#logo")

# Load a batch from glob
ot_image.load_batch(img="~/screenshots/*.png")

# Load a batch from a list
ot_image.load_batch(img=["~/a.png", "~/b.png"])

# List all loaded images
ot_image.list()

# Delete a single image
ot_image.delete(handle="#img_a3f7b2c4")

# Purge images older than 1 hour
ot_image.purge(minutes=60)

# Purge all images
ot_image.purge(all=True)
```

## See Also

- [Vision comparison: img.ask vs direct attachment](../../results/compare-vision.md) — benchmark showing accuracy and token cost trade-offs
