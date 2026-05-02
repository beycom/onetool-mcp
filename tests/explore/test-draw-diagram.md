# Draw a Diagram

Use the diagram pack to create and render a flowchart.

Start with `ot.help()` then `ot.tools(pattern="diagram", info="min")`.

Steps:
1. `diagram.list_providers(focus_only=True)` — see what's available
2. `diagram.get_diagram_instructions(provider="mermaid")` — learn the syntax
3. Create a flowchart showing OneTool's request pipeline: Input → Validate → Execute → Format → Return
4. `diagram.generate_source(source=..., provider="mermaid", name="request-flow")` — save it
5. `diagram.render_diagram(source_file=...)` — render to SVG
6. `diagram.get_playground_url(source=..., provider="mermaid")` — get interactive editor link

Report: table of all diagram tools with purpose and when to use each.
