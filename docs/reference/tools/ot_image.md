# OT Image

Load images and ask vision questions via an OpenAI-compatible API.

Short alias: `img`

## Highlights

- Load bounded images from file paths, URLs, or the clipboard; reference them
  by canonical content handle for follow-up questions
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
| `img` | str | For `load()`: file path, HTTPS URL, or `"clip"`. For `ask()`/`summary()`: those sources or a canonical `"#img_<64 lowercase hex>"` reference |
| `handle` | str | For `delete()` only: canonical `"#img_<64 lowercase hex>"` reference |
| `q` | str \| list[str] | Question(s) to ask. Multiple questions are batched into one model call |
| `img` (in `ask()`) | str \| list[str] | Image reference or list of references (max 8) — a list sends all images in one call for comparison questions; response carries `handles` instead of `handle` |
| `max_edge` | int | Max longest edge in pixels for in-memory model resize. Default: `1568` |
| `all` | bool | `purge(all=True)` deletes all images regardless of age |
| `minutes` | int | `purge(minutes=N)` deletes images older than N minutes. Default: `15` |

## Requires

- A vision model: set `tools.ot_image.model` or the top-level `llm.model` for `ask()`, `summary()`, `clip_ask()`, and `clip_view()`.
- `OPENAI_API_KEY` or `OT_LLM_API_KEY` in `secrets.yaml` for vision model calls.
  The image-specific key takes precedence.

## Configuration

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.ot_image.model` | str | `""` | Vision model for `ask()` and `summary()`. Falls back to `llm.model` |
| `tools.ot_image.base_url` | str | `""` | OpenAI-compatible base URL. Falls back to `llm.base_url` |
| `tools.ot_image.max_edge` | int | `1568` | Maximum longest edge (pixels) for model-upload resize |
| `tools.ot_image.session_cache_size` | positive int | `10` | Exact in-memory LRU cache cap (number of images) |

```yaml
# Minimal — inherits model and base_url from top-level llm: block
llm:
  base_url: https://openrouter.ai/api/v1
  model: google/gemini-2-flash-preview

# Override just for ot_image (optional)
tools:
  ot_image:
    model: openai/gpt-4o-mini   # overrides llm.model for vision calls only
    max_edge: 1568
    session_cache_size: 10
```

### Defaults

- If `tools.ot_image` is omitted, `load()` and `list()` work without config. `ask()` and `summary()` require a model via `tools.ot_image.model` or `llm.model`.
- `model` and `base_url` fall back to the top-level `llm:` config block. The
  API key uses `OPENAI_API_KEY`, then falls back to `OT_LLM_API_KEY`.
- URL originals are streamed and limited to 20 MiB. Declared or observed
  oversize responses return an error without decoding or storing the body.
- Handles are the full SHA-256 digest in the form
  `#img_<64 lowercase hexadecimal characters>`. Short, named, bare, and custom
  handles are not accepted.

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

# Compare two images in one call
before = ot_image.load(img="~/screenshots/before.png")
after = ot_image.load(img="~/screenshots/after.png")
ot_image.ask(
    img=[before["handle"], after["handle"]],
    q="What differs between image 1 and image 2?",
)

# Clipboard shortcuts (no load step needed)
ot_image.clip_ask(q="Extract all text from this screenshot")
ot_image.clip_view()

# Structured summary — cached after first call
ot_image.summary(img=result["handle"])

# Load a batch from glob
ot_image.load_batch(img="~/screenshots/*.png")

# Load a batch from a list
ot_image.load_batch(img=["~/a.png", "~/b.png"])

# List all loaded images
ot_image.list()

# Delete a single image
ot_image.delete(handle=result["handle"])

# Purge images older than 1 hour
ot_image.purge(minutes=60)

# Purge all images
ot_image.purge(all=True)
```

## See Also

- [Vision comparison: img.ask vs direct attachment](../../results/compare-vision.md) — benchmark showing accuracy and token cost trade-offs
