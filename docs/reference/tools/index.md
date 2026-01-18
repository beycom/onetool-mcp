# Tools Reference

**11 namespaces. 50+ functions. Zero tool-selection overhead.**

Every function below is callable with a single `__ot` prefix. No JSON schemas, no tool discovery loops.

## Tool Index

| Namespace | Description | Documentation |
|-----------|-------------|---------------|
| **web** | Content extraction | [web-fetch.md](web-fetch.md) |
| **brave** | Web, news, local search | [brave-search.md](brave-search.md) |
| **ground** | Google grounded search | [grounding-search.md](grounding-search.md) |
| **context7** | Library documentation | [context7.md](context7.md) |
| **code** | Semantic code search | [code-search.md](code-search.md) |
| **ripgrep** | Fast text/regex search | [ripgrep.md](ripgrep.md) |
| **llm** | Data transformation | [transform.md](transform.md) |
| **db** | Database queries | [database.md](database.md) |
| **excel** | Excel manipulation | [excel.md](excel.md) |
| **package** | Package versions | [package.md](package.md) |
| **file** | File operations | [file.md](file.md) |
| **diagram** | Diagram generation | [diagram.md](diagram.md) |
| **ot** | Internal tools | [ot.md](ot.md) |

## Quick Reference

### Web & Search

```python
# Web content extraction
web.fetch(url="https://example.com")
web.fetch_batch(urls=["url1", "url2"])

# Brave search
brave.search(query="AI news", count=10)
brave.news(query="tech", freshness="pd")
brave.local(query="coffee near me")

# Google grounded search
ground.search(query="current weather")
ground.dev(query="React hooks")
```

### Documentation & Code

```python
# Library docs
context7.search(query="next.js routing")
context7.doc(library="/vercel/next.js")

# Code search
code.search(query="authentication handler")
ripgrep.search(pattern="def.*async", path="src/")
```

### Data Processing

```python
# LLM transformation
llm.transform(input=data, prompt="extract emails")

# Database
db.tables(project="myapp")
db.query(project="myapp", sql="SELECT * FROM users")

# Excel
excel.read(path="data.xlsx", sheet="Sheet1")
excel.write(path="output.xlsx", data=rows)
```

### Package Management

```python
package.npm(["react", "vue"])
package.pypi(["requests", "flask"])
package.version(registry="npm", packages={"react": "^18.0.0"})
```

### Diagrams

```python
# Generate and render diagrams
diagram.generate_source(source="...", provider="mermaid", name="flow")
diagram.render_diagram(source="...", provider="mermaid", name="flow")

# Get guidance
diagram.get_diagram_instructions(provider="mermaid")
diagram.get_diagram_policy()
diagram.list_providers()

# Batch rendering (self-hosted only)
diagram.batch_render(sources=[...])
diagram.render_directory(directory="./diagrams")
```

## License Information

| Tool | License |
|------|---------|
| Web Fetch | Apache 2.0 |
| Brave Search | MIT |
| Grounding Search | MIT |
| Context7 | MIT |
| Code Search | MIT |
| Ripgrep | MIT |
| Transform | MIT |
| Database | MPL 2.0 |
| Excel | MIT |
| Package | MIT |
| Diagram | MIT |

Full license texts: [licenses/](../../../licenses/)
