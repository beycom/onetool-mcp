# Snippets

Snippets are reusable code templates — short names that expand into full tool calls. Instead of writing `br.search_batch(queries=["react","vue"], max_results=10)` every time, you write `:br q=react|vue`.

## Loading the Bundled Library

OneTool ships a default snippets library. It is **not loaded automatically** — add it to your `onetool.yaml`:

```yaml
include:
  - config/snippets.yaml
```

`onetool init` writes this for you. If you're writing your own config from scratch, add it manually.

## Listing Snippets

```python
# Names and descriptions
ot.snippets()

# Full params for every snippet
ot.snippets(info="full")

# Filter by name or description
ot.snippets(pattern="search")

# Detail for one snippet (params, body)
ot.snippet_info(name="help")
```

## Running a Snippet

Prefix with `:name` and pass `key=value` params:

```
__onetool :br q=react hooks
__onetool :help q=web search
__onetool :wf url=https://news.ycombinator.com
```

- **Quotes are optional:** `q=react hooks` ≡ `q="react hooks"`
- **Prefix abbreviation:** `co` resolves to `context`, `pa` to `path`, etc. if unambiguous
- **Pipe separates multiple values** in batch snippets: `:br q=react|vue|svelte`
- **Snippet input is not Python:** values are plain strings until the snippet template renders Python

### Snippets Inside Python Workflows

Inside code mode, execute snippet commands with the nested `__onetool(...)` helper:

```python
__onetool(":help q=web search")
__onetool(":wf url=https://docs.python.org")
```

## Standard Snippets

All snippets included in `config/snippets.yaml`:

### Search

| Snippet | Description | Key params |
|---------|-------------|------------|
| `:br` | Brave batch search | `q` (pipe-sep), `count` |
| `:c7` | Context7 library docs | `lib`, `q` |
| `:g` | Gemini grounded search | `q` (pipe-sep), `tech`, `focus` |
| `:tav` | Tavily AI search | `q` (pipe-sep), `depth`, `count` |
| `:tav_x` | Tavily URL extraction | `url` (pipe-sep), `depth` |

### Files & Code

| Snippet | Description | Key params |
|---------|-------------|------------|
| `:f_r` | Read a file | `path`, `offset`, `limit` |
| `:f_t` | Directory tree | `path`, `depth` |
| `:f_g` | Grep file contents | `p`, `path`, `glob`, `i` |
| `:cv` | Convert docs to markdown | `file`, `output_dir` |

### Web

| Snippet | Description | Key params |
|---------|-------------|------------|
| `:wf` | Fetch URL(s) | `url` (pipe-sep), `format`, `links`, `max` |
| `:wf_d` | Extract structured data from a page | `url`, `schema` |
| `:wf_s` | Fetch and summarize a page | `url`, `focus` |

### Packages & Models

| Snippet | Description | Key params |
|---------|-------------|------------|
| `:pkg_a` | Audit project dependencies | `path` |
| `:pkg_npm` | npm package versions | `packages` (comma-sep) |
| `:pkg_py` | PyPI package versions | `packages` (comma-sep) |
| `:pkg_m` | Search AI models on OpenRouter | `q`, `provider` |

### Memory

| Snippet | Description | Key params |
|---------|-------------|------------|
| `:mem_s` | Semantic search across memories | `q`, `mode`, `topic` |
| `:mem_g` | Regex grep memory content | `p`, `topic`, `i` |
| `:mem_r` | Read a memory topic | `topic`, `meta` |
| `:mem_w` | Write a file into memory | `topic`, `file`, `category` |
| `:mem_l` | List all memory topics | — |

### System

| Snippet | Description | Key params |
|---------|-------------|------------|
| `:help` | Search OneTool help | `q`, `info` |
| `:tool` | Show tool signature or search tools | `name`, `pattern`, `info` |
| `:servers` | List MCP proxy server status | `pattern`, `info` |
| `:server_on` | Enable a configured MCP proxy server | `name` |
| `:server_off` | Disable a configured MCP proxy server | `name` |
| `:reload` | Reload OneTool configuration | — |
| `:status` | Show system health and config | — |

## Examples

```
# Search multiple topics at once
__onetool :br q=react hooks|vue composition api|svelte

# Discover a tool signature
__onetool :tool name=brave.search info=full

# Fetch and summarize a page, focused on a specific area
__onetool :wf_s url=https://news.ycombinator.com focus=pricing

# Check latest npm package versions
__onetool :pkg_npm packages=react,typescript,vite

# Semantic search across memories
__onetool :mem_s q=authentication patterns

# Enable a configured proxy server for this session
__onetool :server_on name=playwright
```

## Defining Your Own Snippets

Add snippets directly to your `onetool.yaml`:

```yaml
snippets:
  my_search:
    description: Search with preferred settings
    params:
      q: { description: "Search query" }
    body: |
      br.search(query="{{ q }}", max_results=5)
```

Inline snippets override any snippet with the same name from included files.

See [Configuration Reference](../reference/cli/onetool-config.md#snippets) for the full YAML schema.
