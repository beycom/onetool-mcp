# Tool Reference Documentation

Standard format for `docs/reference/tools/<pack>.md` files. Follow this structure exactly so all tool docs are consistent.

---

## File Location

```
docs/reference/tools/<pack-name>.md
```

One file per pack. The filename matches the pack name (e.g., `brave.md` for `pack = "brave"`).

---

## Structure

Every reference doc contains these sections in order:

```
# <Pack Name>

<One-line description>

## Highlights
## Functions
## Key Parameters
## Requires
## Configuration
## Examples
## CLI         ← only when the pack ships onetool subcommands
```

---

## Section Reference

### Title and description

```markdown
# Brave Search

Web, news, image, and video search via Brave Search API.
```

- Pack name in title case
- One sentence only — what it does and via what API/service
- If the pack has a short alias, show it in the subtitle or first paragraph: `ot_context` (`ctx`), `ot_image` (`img`)
- In body text and tables, always lead with the full pack name — see [Pack Naming Convention](../../practices/docs-writing.md#pack-naming-convention)

---

### ## Highlights

3–4 bullet points. Lead with the most useful capabilities:

```markdown
## Highlights

- Four search types: web, news, image, video
- Batch search with concurrent execution
- Query validation (400 char / 50 word limits)
```

---

### ## Functions

Table of all public functions. Use `pack.func(required_arg, ...)` style — include the first required arg, then `...` for the rest:

```markdown
## Functions

| Function | Description |
|----------|-------------|
| `brave.search(query, ...)` | General web search |
| `brave.news(query, ...)` | News articles (sorted by recency) |
| `brave.search_batch(queries, ...)` | Multiple searches concurrently |
```

---

### ## Key Parameters

Table of the most important parameters across the pack's functions. Omit obvious or rarely-used params. Include the accepted values for enum-like params:

```markdown
## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | str | Search query (max 400 chars, 50 words) |
| `count` | int | Results per query (1-20) |
| `freshness` | str | "pd" (day), "pw" (week), "pm" (month), "py" (year) |
| `safesearch` | str | "off", "moderate", "strict" |
```

---

### ## Requires

Quick bullet list of hard requirements (secrets, external binaries):

```markdown
## Requires

- `BRAVE_API_KEY` in secrets.yaml
```

---

### ## Configuration

Full configuration reference. Always include all three subsections:

```markdown
## Configuration

### Required

- `BRAVE_API_KEY` must be set in `secrets.yaml`.

### Optional

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `tools.brave.timeout` | float | `60.0` | Request timeout in seconds. Range: `1.0-300.0`. |

```yaml
tools:
  brave:
    timeout: 60.0
```

### Defaults

- If `tools.brave` is omitted, Brave uses the built-in timeout shown above.
```

**Rules:**
- `### Required` — list every secret that must be set. If there are none, write "None — no secrets required."
- `### Optional` — one row per config key supported by the pack's `Config` class. Use the full dotted key path (`tools.<pack>.<field>`). Include the range/constraints in the description.
- The yaml block shows only the optional keys with their defaults.
- `### Defaults` — one sentence per optional key describing fallback behaviour.

---

### ## Examples

Realistic, runnable examples. Cover the main use cases including batch and any specialized functions. Use comments to explain what each block does:

```markdown
## Examples

```python
# Basic search
brave.search(query="python async tutorial", count=10)

# News with freshness filter
brave.news(query="AI announcements", freshness="pw")

# Batch search
brave.search_batch(queries=["react hooks", "vue composition api"])
```
```

**Rules:**
- 3–6 examples minimum for search-type packs; 1–3 for simpler utility packs
- Each example has a `# comment` explaining the use case
- Show at least one batch/multi-item call if the pack has one
- Show domain filters, output format options, or other important optional params if present

When documenting tools that do concurrent, async, or background work, describe the user-facing synchronous contract rather than the implementation detail. For example, say "renders files concurrently and returns when complete" for sync batch work, or "starts a background render and returns a task ID" only when the function actually returns before work completes and has a status function that can observe progress.

If a function queues work, document how users can check completion, failures, pending items, dropped jobs, or timeouts. Do not describe a blocking function as async just because it uses threads or async libraries internally.

---

### ## CLI

Include a `## CLI` section **only** when the pack ships one or more `onetool <pack>` subcommands (i.e. it registers a Typer sub-app in `onetool/kb.py` or similar). Place it after `## Examples`.

```markdown
## CLI

<One-line description of what the CLI group does. Mention auto-detection if applicable.>

### Global options

| Option | Description |
|--------|-------------|
| `-c, --config PATH` | … |
| `-s, --secrets PATH` | … |

### onetool <pack> <command>

<One-sentence description.>

```bash
onetool <pack> <command> <arg> [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--foo TEXT` | … |

```bash
# Usage examples (1–3 lines)
onetool <pack> <command> mydb
```
```

**Rules:**
- One `### onetool <pack> <command>` subsection per subcommand
- List every option with its type and default; mark required options
- Show 1–3 concrete bash examples per subcommand
- If a subcommand requires an extra or an external binary, note it in the subsection intro (e.g. "Requires the `onetool-mcp[scrape]` extra and `playwright install chromium`.")
- Do **not** duplicate this content in `docs/reference/cli/` — the tool reference page is the single source of truth for pack CLIs

---

## Checklist

When creating or updating a tool reference doc:

- [ ] File at `docs/reference/tools/<pack>.md`
- [ ] Title = pack name in title case + one-liner description
- [ ] Short alias shown as `full_name (alias)` — never alias alone in narrative or tables
- [ ] `## Highlights` — 3–4 bullets
- [ ] `## Functions` — table covers all public functions in `__all__`
- [ ] `## Key Parameters` — covers the most useful params
- [ ] `## Requires` — secrets from `__ot_requires__["secrets"]`; Python extras from `pyproject.toml` optional-dependencies
- [ ] `## Configuration` — `### Required`, `### Optional`, yaml block, `### Defaults`
- [ ] Optional table keys match fields in the pack's `Config` class
- [ ] `## Examples` — at least 3 realistic examples, comments on each
- [ ] `## CLI` — present if the pack registers an `onetool <pack>` subcommand group; omit otherwise
- [ ] All function names, param names, and default values match the source code

---

**Related:**
- [Creating Tools](tool-development.md) — full tool creation guide
- [Tool Configuration](tool-configuration.md) — adding config to tools
