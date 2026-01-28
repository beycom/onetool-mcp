# Tools Reference

**16 packs. 90+ tools. Zero tool-selection overhead.**

Every function below is callable with a single `__ot` prefix. No JSON schemas, no tool discovery loops.

## Tool Index

| Pack | Description | Documentation |
|-----------|-------------|---------------|
| **brave** | Web, news, local search | [brave.md](brave.md) |
| **code** | Semantic code search | [code.md](code.md) |
| **context7** | Library documentation | [context7.md](context7.md) |
| **convert** | Document to Markdown | [convert.md](convert.md) |
| **db** | Database queries | [db.md](db.md) |
| **diagram** | Diagram generation | [diagram.md](diagram.md) |
| **excel** | Excel manipulation | [excel.md](excel.md) |
| **file** | File operations | [file.md](file.md) |
| **firecrawl** | Web scraping & crawling | [firecrawl.md](firecrawl.md) |
| **ground** | Google grounded search | [ground.md](ground.md) |
| **llm** | Data transformation | [llm.md](llm.md) |
| **ot** | Internal tools | [ot.md](ot.md) |
| **package** | Package versions | [package.md](package.md) |
| **ripgrep** | Fast text/regex search | [ripgrep.md](ripgrep.md) |
| **scaffold** | Extension scaffolding | [scaffold.md](scaffold.md) |
| **web** | Content extraction | [web.md](web.md) |

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
db.tables(db_url="sqlite:///data.db")
db.query(sql="SELECT * FROM users", db_url="sqlite:///data.db")

# Excel
excel.read(path="data.xlsx", sheet="Sheet1")
excel.write(path="output.xlsx", data=rows)
```

### Document Conversion

```python
# Convert documents to Markdown
convert.pdf(pattern="report.pdf", output_dir="output")
convert.word(pattern="doc.docx", output_dir="output")
convert.powerpoint(pattern="deck.pptx", output_dir="output")
convert.excel(pattern="data.xlsx", output_dir="output")

# Auto-detect format
convert.auto(pattern="documents/*", output_dir="converted")
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
| Convert | MIT |
| Package | MIT |
| Diagram | MIT |
| Firecrawl | AGPL-3.0 |

Full license texts: [licenses/](https://github.com/beycom/onetool/tree/main/licenses)
