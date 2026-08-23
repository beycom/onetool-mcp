# Arch

Architecture schema-v3 file workflows: validate a YAML architecture model, resolve its state at any milestone, diff two states, and advance the baseline as milestones complete.

## Highlights

- Single-file YAML model (`schema_version: 3`) holding milestones, optional timelines, and six entity kinds: systems, subsystems, components, users, interfaces, relationships
- Entities carry `from`/`until` milestone intervals; revisions of the same id describe how an entity changes over time
- `resolve` returns the full entity state at `current`, any milestone, or `end`, with liveness clipping and authored root causes
- `diff` compares any two states — added, removed, and field-level changes
- `advance` deterministically rewrites the file after a milestone is delivered, folding it into the baseline
- `validate` reports structural errors and advisory warnings with stable codes and `file:line:column` locations
- Deterministic YAML output: round-trips are idempotent

## Functions

```python
arch.init(output_path: str)  # Create a minimal schema-v3 YAML file (refuses to overwrite).
arch.validate(input_path: str)  # Structural errors + advisory warnings with locations.
arch.resolve(input_path: str, at: str = "current", timeline: str | None = None)  # Entity state at a position.
arch.diff(input_path: str, at_a: str = "current", at_b: str = "end", timeline_a: str | None = None, timeline_b: str | None = None)  # Diff two states.
arch.advance(input_path: str, through: str)  # Fold a delivered milestone into the baseline and rewrite the file.
```

State selectors accept `current` (baseline), a milestone id, or `end` (after the last milestone). When the model declares multiple timelines, pass the timeline id.

## Dev CLI

The same operations are available without MCP:

```bash
python -m otdev.tools._arch.v3 validate model.yaml [--json]
python -m otdev.tools._arch.v3 resolve model.yaml --at <milestone> [--json]
python -m otdev.tools._arch.v3 diff model.yaml --at-a current --at-b end [--json]
python -m otdev.tools._arch.v3 advance model.yaml --through <milestone>
```
