# OT Caveman

LLM-powered text compaction and expansion. Reduces verbose prose by 20–80% while
preserving all meaning, protected content (code blocks, URLs, error messages, security
warnings) is never modified.

Short alias: `cm`

## Highlights

- Most explicit protected-content rules of any text-compaction tool — code blocks, URLs,
  file paths, commands, version numbers, error messages, security warnings, proper nouns,
  markdown headings, checklist items, and emoji indicators are all named and never modified
- Only text-compaction tool with an `expand()` inverse — packed text can be reconstructed
  to readable prose
- Only tool with a built-in command queue reader — `input()` reads and marks-done commands
  from a `command.md` task file, enabling agent-driven workflows
- Works with any OpenAI-compatible endpoint — not tied to a specific provider or model
- Token stats on every call (`tokens_in`, `tokens_out`, `reduction_pct`)
- File-to-file compaction with optional in-place overwrite; glob batch mode for entire directories

> **Note on tool naming**: The compaction tool is named `compact` (not `pack`) to avoid
> a Python naming conflict with the module-level `pack = "ot_caveman"` variable.
> Use `cm.compact(...)`, `cm.expand(...)`, `cm.input(...)`.

## Functions

| Function | Description |
|----------|-------------|
| `ot_caveman.compact(text, ...)` | Compact text or a file to terse caveman-speak |
| `ot_caveman.expand(text, ...)` | Expand packed text back to readable prose |
| `ot_caveman.input(file, ...)` | Read next pending command from a command.md queue file |

## compact()

```python
cm.compact(
    text=None,          # inline text to compact (mutually exclusive with src)
    src=None,           # path to file to compact; supports glob patterns (*.md)
    dest=None,          # path to write result (optional; may equal src for in-place)
                        # for glob src: treated as output directory
    overwrite=False,    # for glob src: write each result in-place instead of <stem>-min.<ext>
)
```

Returns a dict:
```python
{
    "text": str,            # compacted text (original if unchanged)
    "tokens_in": int,       # input token count (tiktoken)
    "tokens_out": int,      # output token count
    "reduction_pct": int,   # percentage reduction (0 when unchanged)
    "unchanged": True,      # only present when output was rejected and original returned
    "file_out": str,        # only present when dest was given
    "cost_saved_usd": float # only present when tools.ot_caveman.cost_per_1m_tokens is set
}
```

`unchanged: True` means the LLM output failed a post-processing check (dropped code blocks,
returned empty, or expanded the content) and the original was returned verbatim.

For glob `src`, returns a batch summary:
```python
{
    "files": int,           # files successfully processed
    "skipped": int,         # files skipped (empty, unreadable, or API error)
    "unchanged": int,       # only present when >0 files fell back to original
    "tokens_in": int,
    "tokens_out": int,
    "reduction_pct": int,
    "cost_saved_usd": float # only when cost_per_1m_tokens is set
}
```

Returns an error string on misconfiguration or failure.

### Protected content (never altered)

- **Fenced code blocks** — extracted before compaction, restored verbatim after. The LLM
  sees only a `[!PLACEHOLDER:N!]` marker. Guarantees preservation regardless of model behaviour.
- **Markdown tables** — extracted, column-padding normalized (saves 10–30% of table tokens),
  then restored verbatim via `[!TABLE:N!]` markers. Separator rows collapsed to `|---|---|`.
- URLs and file paths
- Shell commands and version numbers
- Technical identifiers and numbers
- Error messages and stack traces
- Proper nouns
- Security warnings and irreversible action descriptions
- Markdown headings (`#` / `##` / `###` lines)
- Markdown checklists (`- [ ]` / `- [x]` items)
- Emoji indicators (✅, ❌, ⚠️, etc.) used as list markers — never replaced with `[ ]` or removed

## expand()

```python
cm.expand(
    text=None,      # inline packed text to expand (mutually exclusive with src)
    src=None,       # path to file containing packed text; supports glob patterns
    dest=None,      # path to write expanded result (optional)
                    # for glob src: treated as output directory
    overwrite=False # for glob src: write each result in-place
)
```

Returns a dict:
```python
{
    "text": str,            # expanded prose
    "tokens_in": int,
    "tokens_out": int,
    "expansion_pct": int,   # percentage expansion (positive for typical packed input)
    "file_out": str,        # only present when dest was given
    "cost_saved_usd": float # only when cost_per_1m_tokens is set
}
```

**Reconstruction is lossy** — does not attempt to restore original wording. Protected
content (code blocks, headings, etc.) is preserved verbatim.

## input()

```python
cm.input(
    file="command.md",  # path to command queue file (relative to cwd)
    command=None,       # if set, retrieve the named block by name:<tag> instead of
                        # sequential queue; does not modify the file
    compact=True,       # compact returned text using ot_caveman_input_compact prompt
                        # pass compact=False to get raw text
)
```

Reads the next pending command block from a `command.md`-style file. Command blocks are
separated by `---` dividers. A pending block is one whose title line does **not** start
with `[x]`.

Returns the pending command's text (optionally compacted) and marks it done in the file
by prepending `[x] ` to its title. Header lines starting with `# ` are skipped.

Returns `"NO MORE COMMANDS"` when all blocks are done, or an error string if the file
is not found.

**Note:** `compact=True` (the default) makes an LLM call. Pass `compact=False` to get
raw text without an API call.

### command.md format

```markdown
# Commands

Build the auth module
Write unit tests and integration tests.

---

[x] Add logging middleware
Already done.

---

Deploy to staging
Use the blue-green strategy.
```

In this example, `cm.input(compact=False)` returns `"Build the auth module\nWrite unit tests and integration tests."` and marks it `[x]`.

### Named command blocks

Command blocks support an optional `name:<tag>` first line:

```markdown
---
name:fix
/p:fix all issues in wip/issues/1-new/*.md
All well spec'ed so no need for user approval
---
name:review
Review the latest PR and summarise changes
---
```

`cm.input(command="fix", compact=False)` finds the `name:fix` block regardless of `[x]`
status, returns its body text (excluding the `name:` line), and does **not** modify the file.
Named commands can be re-invoked on demand.

## Modes of use

There are four ways to apply caveman compaction:

| Mode | How | When |
|------|-----|------|
| **Explicit call** | `cm.compact(text=...)` or `cm.compact(src=...)` | One-off compaction of a specific value or file |
| **Ask compact** | `ctx.ask(handle, q=...)` then `cm.compact(text=answer)` | Compact an LLM answer about stored search/fetch results |
| **`__compact__` dunder** | `__compact__ = True` at the top of a code block | Compact the entire output of a code block automatically |
| **`/ot_cm` skill** | `/ot_cm` in chat | Switch Claude's own responses to terse caveman-speak for the session |

### Explicit call

Direct compaction of a string or file. Returns a dict with `text`, `tokens_in`, `tokens_out`,
`reduction_pct`. See `compact()` and `expand()` above.

```python
result = cm.compact(text=some_long_output)
print(result["text"])           # compacted text
print(result["reduction_pct"]) # e.g. 42
```

### Ask compact

Compact the output of `ctx.ask()` after asking a question about stored search results.
Keep `__compact__` dunder OFF — only the ask answer is compacted, not the whole block.

```python
# 1. Store big search results
h = ctx.write(content=str(brave.search(query='Python async best practices', count=10)))

# 2. Ask a question — no dunder
answer = ctx.ask(h['handle'], q='What are the top 5 best practices?')['result'][0]['answer']

# 3. Compact the answer explicitly
slim = cm.compact(text=answer)
slim['text']  # terse answer; slim['reduction_pct'] typically 25–30%
```

This pattern also applies to `ground.search`, `webfetch.fetch`, or any tool that returns
large text that you first store with `ctx.write()`.

### `__compact__` dunder

Setting `__compact__ = True` at the top of a code block compacts the entire serialized output
before it is returned to the caller. No `cm.compact()` call needed.

```python
__compact__ = True
brave.search(query='asyncio best practices', count=10)
# → output is compacted in-place before being returned; ~25–31% reduction on search snippets
```

`__compact__ = False` explicitly disables compaction even when `output.compact: true` is set
in config (see below).

The dunder is validated by the security layer (`__compact__` is in `allowed_dunders`) and
applied after serialization but before the ctx-store threshold check — so the compacted
form is what gets stored if the output is large.

**When to use the dunder vs explicit call:**

- Use the dunder when you want the whole block output compacted and don't need the token stats.
- Use `cm.compact()` explicitly when you need `tokens_in`/`tokens_out`/`reduction_pct` or
  are compacting only part of a result (e.g., just the ask answer, not the handle metadata).

### `output.compact` config default

Set `output.compact: true` in `onetool.yaml` to apply compaction to every code block output
by default, without setting `__compact__ = True` each time:

```yaml
# onetool.yaml
output:
  compact: true   # apply ot_caveman compaction to all outputs by default
```

Override per-call with `__compact__ = False` to skip compaction for a specific block.

### `/ot_cm` skill

The `/ot_cm` skill switches Claude's own prose responses to terse caveman-speak for the rest
of the session. It is a Claude behavioural instruction — it does not call `cm.compact()` and
does not count tokens.

```
/ot_cm
```

Apply at the start of a session to reduce verbose explanations in Claude's replies.
Protected content rules (code blocks, URLs, headings, identifiers, etc.) are identical to
those used by `cm.compact()` — the same things are never altered.

---

## Requires

Configuration (tool not available until all are set):
- `OPENAI_API_KEY` in `secrets.yaml`
- `base_url` — set via top-level `llm.base_url` or `tools.ot_caveman.base_url`
- `model` — set via top-level `llm.model` or `tools.ot_caveman.model`

Python packages: `openai`, `tiktoken`

## Configuration

```yaml
# onetool.yaml
tools:
  ot_caveman:
    model: ""               # overrides llm.model; empty = inherit
    base_url: ""            # overrides llm.base_url; empty = inherit
    timeout: 30             # API timeout in seconds (default: 30)
    max_tokens: 8192        # max response tokens (default: 8192)
    cost_per_1m_tokens: 0.0 # when non-zero, adds cost_saved_usd to results
```

`model` and `base_url` inherit from the top-level `llm:` block when empty.
`timeout`, `max_tokens`, and `cost_per_1m_tokens` are pack-specific — no global fallback.

### Tweaking compaction rules

Compaction behaviour is driven by four prompt templates in `global_templates/prompts.yaml`.
Override any of them in `.onetool/prompts.yaml` under `templates:`:

| Template key | Used by | Controls |
|---|---|---|
| `ot_caveman_compact` | `cm.compact()`, `__compact__` dunder | System prompt for output/file compaction — defines what to drop, compress, and preserve |
| `ot_caveman_expand` | `cm.expand()` | System prompt for expansion back to readable prose |
| `ot_caveman_compact_input` | `cm.compact()` only | User message wrapper: `"Compact the following text:\n\n{content}"` — rarely needs changing |
| `ot_caveman_input_compact` | `cm.input(compact=True)` | System prompt for command queue compaction — same drop/preserve rules, targets 40–60% reduction |

**Example — make compaction more aggressive** (drop more connective tissue):

```yaml
# .onetool/prompts.yaml
templates:
  ot_caveman_compact: |
    You are a text compaction assistant. Compact to absolute minimum tokens.
    Drop: articles, filler, hedging, connectives, redundant examples.
    Preserve EXACTLY: code blocks, inline code, URLs, paths, identifiers, numbers, errors, headings.
    One word when one word is enough. Fragments OK.
    Output ONLY the compacted text.
```

**Example — preserve more detail in answers** (less aggressive, keeps examples):

```yaml
# .onetool/prompts.yaml
templates:
  ot_caveman_compact: |
    You are a text compaction assistant. Remove only filler and redundancy.
    Keep all examples, all numbered items, and all parenthetical clarifications.
    Preserve EXACTLY: code blocks, inline code, URLs, paths, identifiers, errors, headings.
    Do NOT use arrow notation or fragments — keep complete sentences.
    Output ONLY the compacted text.
```

The default templates are in `src/ot/config/global_templates/prompts.yaml` and serve as
the canonical reference for what each rule does.

## Typical reduction by content type

Measured on live outputs. All use the default prompt templates.

| Content type | Typical reduction | Notes |
|---|---|---|
| Verbose tech prose (no code) | 55–65% | Strongest gains — hedging and filler stripped |
| Conversational prose | 45–55% | Articles, connectives, pleasantries removed |
| Mixed prose + code | 15–35% | Depends on prose/code ratio; fences not compacted |
| Multi-fence docs (guides) | 15–20% | Low because protected fence volume dominates token count |
| `brave.search` results (10 items) | 25–31% | Snippets trimmed; URLs and titles preserved verbatim |
| `ground.search` results (5 sources) | 20–25% | Structured content with embedded code; may still hit ctx threshold |
| `ctx.ask` answer | 25–30% | Rules/facts preserved; minor parenthetical examples may be trimmed |
| Already-terse text | 0% | `unchanged: true` returned; original preserved |
| Ripgrep / structured output | 0% | File:line:match format is already maximal density |
| Markdown tables | 10–20% | Cell content intact; separator padding stripped (saves 10–30% of table tokens alone) |

**Code-dense files see low reduction by design** — fenced code blocks are extracted before the
LLM call and restored verbatim, so only the inter-fence prose is compacted. A file that is
80% code will see ~10–15% overall reduction regardless of prompt settings.

## Examples

```python
# Compact a long response inline
cm.compact(text=some_long_response)

# Compact a file (in-place)
cm.compact(src="notes.md", dest="notes.md")

# Compact to a separate slim file
cm.compact(src="context.md", dest="context-slim.md")

# Compact a whole directory of guides
cm.compact(src="dev/guides/*.md", dest="scratch/compact")

# Compact all guides in-place
cm.compact(src="dev/guides/*.md", overwrite=True)

# Expand packed content back to prose
cm.expand(text="meeting discuss matters. follow-up needed policy changes.")

# Expand a file
cm.expand(src="context-slim.md", dest="context-expanded.md")

# Read next command from queue (raw text, no LLM call)
cmd = cm.input(compact=False)
# cmd = "Build the auth module\nWrite unit tests and integration tests."

# Read next command, auto-compacted for context efficiency
cmd = cm.input()

# Re-invoke a named command
cmd = cm.input(command="fix", compact=False)

# Use a custom command file
cmd = cm.input(file="tasks/sprint.md", compact=False)

# Chain: compact a long tool result before storing
result = brave.search(query="AI news today", count=20)
slim = cm.compact(text=str(result))
mem.write(topic="ai-news", content=slim["text"])
```
