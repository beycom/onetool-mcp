# Examples

**Copy. Paste. Run.**

Working examples for every use case. The `demo/` folder is your playground.

## Use Cases

| Category | Tools | Example |
|----------|-------|---------|
| **Web Research** | `brave.search`, `web.fetch` | `brave.search(query="AI trends 2026")` |
| **Documentation** | `context7.search`, `context7.doc` | `context7.doc(library="/vercel/next.js")` |
| **Code Analysis** | `code.search`, `ripgrep.search` | `ripgrep.search(pattern="def.*async")` |
| **Data Processing** | `llm.transform`, `db.query` | `llm.transform(input=data, prompt="extract emails")` |
| **Package Management** | `package.npm`, `package.pypi` | `package.npm(["react", "vue"])` |

## Demo Project

The `demo/` folder provides sample configurations and data for testing OneTool CLIs.

## Using the Demo Project

Set `OT_CWD=demo` to use the demo project's configurations:

```bash
# Run benchmarks with demo config
OT_CWD=demo uv run bench run demo/bench/features.yaml

# Start server with demo config
OT_CWD=demo uv run onetool

```

Or use the justfile shortcuts:

```bash
just eg-bench          # TUI picker for demo benchmarks
just eg-serve          # Start server with demo config
```

## Folder Structure

```
demo/
  .onetool/           # OneTool configuration
    onetool.yaml     # MCP server config
    bench.yaml     # Benchmark harness config
    prompts.yaml      # Prompt templates
  bench/              # Benchmark YAML files
  db/                 # Sample databases
```

## demo/bench

Benchmark harness configurations for testing LLM + MCP server combinations.

### Files

| File | Description |
|------|-------------|
| `features.yaml` | Feature showcase (search, docs, transform) |
| `compare.yaml` | Compare base vs OneTool responses |
| `python_exec.yaml` | Python code execution tests |
| `tool_*.yaml` | Per-tool benchmarks |

### Running

```bash
# With TUI picker
just eg-bench

# Specific file
just eg-bench-run features.yaml

# Direct command
OT_CWD=demo uv run bench run demo/bench/tool_brave_search.yaml
```

## demo/db

Sample SQLite database for testing db tools.

| File           | Description                       |
|----------------|-----------------------------------|
| `northwind.db` | Classic Northwind sample database |

```bash
# Run db tool benchmark
just eg-bench-run tool_db.yaml
```
