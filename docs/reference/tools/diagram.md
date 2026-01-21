# Diagram

**Professional diagrams from text descriptions. No ASCII art.**

Generates and renders diagrams using Kroki as the unified backend, supporting Mermaid, PlantUML, D2, and 25+ other diagram types.

## Highlights

- Two-stage pipeline (generate source, then render)
- Config-driven instructions and templates
- Policy rules for LLM guidance
- Batch operations for self-hosted backends
- Playground URL generation for debugging

## Two-Stage Pipeline

| Function | Description |
|----------|-------------|
| `diagram.generate_source(source, provider, name)` | Save source for review |
| `diagram.render_diagram(source, provider, name)` | Render via Kroki |
| `diagram.get_render_status(task_id)` | Check async render progress |

## Batch Operations (Self-Hosted Only)

| Function | Description |
|----------|-------------|
| `diagram.batch_render(sources)` | Render multiple diagrams concurrently |
| `diagram.render_directory(directory)` | Render all source files in a directory |

## Configuration Tools

| Function | Description |
|----------|-------------|
| `diagram.get_diagram_policy()` | Get policy rules for diagram generation |
| `diagram.get_diagram_instructions(provider)` | Get provider-specific guidance |
| `diagram.get_output_config()` | Get output settings |
| `diagram.get_template(name)` | Load a named template |
| `diagram.list_providers(focus_only)` | List available providers |

## Utility Tools

| Function | Description |
|----------|-------------|
| `diagram.get_playground_url(source, provider)` | Get interactive editor URL |

## Focus Providers

- **Mermaid**: Flowcharts, sequences, state diagrams, Gantt, mindmaps
- **PlantUML**: UML diagrams, C4 architecture (via stdlib)
- **D2**: Modern architecture diagrams with auto-layout

All 28+ Kroki providers are available for advanced use.

## Key Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `source` | str | Diagram source code |
| `provider` | str | mermaid, plantuml, d2, graphviz, etc. |
| `output_format` | str | svg (default), png, pdf |
| `output_dir` | str | Override default output directory |
| `async_mode` | bool | Return task ID for status polling |

## Examples

```python
# Generate source for review
diagram.generate_source(
    source="graph TD\n  A --> B",
    provider="mermaid",
    name="flow"
)

# Render diagram
diagram.render_diagram(
    source="graph TD\n  A --> B",
    provider="mermaid",
    name="flow"
)

# Get playground URL for debugging
diagram.get_playground_url(source="graph TD\n  A --> B", provider="mermaid")

# List available providers
diagram.list_providers(focus_only=True)
```

## Configuration

Add to `ot-serve.yaml`:

```yaml
tools:
  diagram:
    backend:
      prefer: remote  # remote | self_hosted | auto
    output:
      dir: ../diagrams  # Relative to config dir
      default_format: svg
```

Or use `include:` to load from a shared config file:

```yaml
include:
  - resources/config/diagram.yaml  # contains tools: {diagram: ...}
```

## Self-Hosted Setup

For batch operations or high-volume rendering, use the Kroki docker-compose from [kroki.io](https://kroki.io/#install):

```bash
# Download Kroki docker-compose
curl -LO https://raw.githubusercontent.com/yuzutech/kroki/main/docker-compose.yml

# Start Kroki
docker compose up -d
```

Then configure `ot-serve.yaml`:

```yaml
tools:
  diagram:
    backend:
      prefer: self_hosted
      self_hosted_url: http://localhost:8000
```

## Source

[Kroki](https://kroki.io/) | [Mermaid](https://mermaid.js.org/) | [PlantUML](https://plantuml.com/) | [D2](https://d2lang.com/)
