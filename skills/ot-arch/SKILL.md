---
name: ot-arch
description: Model, validate, compare, visualize, export, and bundle solution architecture with OneTool's schema-v2 arch pack. Use when creating or maintaining YAML/Excel architecture workspaces, documenting current and target states, delivery changes and roadmaps, producing offline LikeC4 explorers or SVG/Draw.io artifacts, reviewing architecture quality, or preparing portable architecture handoffs.
---

# OneTool Solution Architecture

Use the `arch` pack as a model-first documentation system. Keep architecture facts in complete
states, delivery intent in sparse changes, ordering in roadmaps, audience-specific questions in
views, and presentation-only flows in the diagram catalog.

Invoke operations through OneTool's `run` surface as `arch.operation(keyword=value)`. Use keyword
arguments only. Inspect the live contract with `ot.tool_info(name='arch.operation')` when needed;
do not use removed v1 snapshot, revision, project-scope, deployment, or D2 contracts.

## Follow the core workflow

1. Define the documentation goal and audience before choosing views or exports.
2. Initialize an empty workspace or identify the authoritative schema-v2 YAML/Excel source.
3. Author the complete baseline, sparse changes, ordered roadmaps, reusable views, and diagrams.
4. Run `arch.validate` after each meaningful edit and before every publication step.
5. Use `arch.resolve` and `arch.diff` to prove target states and delivery deltas.
6. Use `arch.generate` for exploration and `arch.export` for review or interchange artifacts.
7. Use `arch.bundle` for an offline, reproducible handoff.

For a new solution:

```python
arch.init(output_path='architecture')
arch.validate(input_path='architecture/architecture.yaml')
```

Initialize only into an empty directory. The result contains paired YAML/Excel examples plus
`views/`, `styles/`, and local asset directories. Choose one source as authoritative, pass that
file explicitly, and refresh the counterpart with `arch.convert`; never edit both independently.
Directory input prefers `architecture.yaml` when the paired files coexist.

## Author the canonical model

Use this shape as the starting point and retain stable IDs across every state, change, view, and
artifact:

```yaml
schema_version: 2
states:
  - id: payments-baseline
    name: Payments baseline
    systems:
      - id: checkout
        name: Checkout
        description: Accepts and coordinates customer orders
      - id: payment-gateway
        name: Payment Gateway
        description: Authorizes payment requests
    applications:
      - id: checkout-api
        name: Checkout API
        system: checkout
        technology: Python
      - id: gateway-api
        name: Gateway API
        system: payment-gateway
    interfaces:
      - id: checkout-to-gateway
        name: Authorize payment
        provider: gateway-api
        consumer: checkout-api
        direction: provider_to_consumer
        type: api
changes:
  - id: introduce-payment-orchestrator
    name: Introduce payment orchestrator
    owner: Payments team
    status: planned
    patches:
      systems:
        - id: payment-orchestrator
          change_type: added
          name: Payment Orchestrator
          description: Coordinates payment providers and retries
roadmaps:
  - id: preferred
    base: payments-baseline
    items:
      - change: introduce-payment-orchestrator
        order: 1
views:
  - id: target-state
    name: Target state
    roadmap: preferred
    through: introduce-payment-orchestrator
```

Keep presentation out of the workspace and Excel domain sheets. Configure explorer defaults,
themes, palettes, and tables under `tools.arch.presentation` in OneTool YAML.

```yaml
tools:
  arch:
    presentation:
      title: Payments platform architecture  # optional; defaults to the input filename stem
      default_roadmap: preferred
      default_theme: clean
      default_selection:
        system_set:
          system_groups: [payments]
        interface_depth: 1
        level: system
        color_by: change_status
      palettes:
        integration_type:
          api: {color: "#3B82F6"}
        tag:
          critical: {color: "#DC2626"}
```

Apply these authoring rules:

- Treat every state as complete. Do not copy unchanged content into changes.
- Treat every change as an independently understandable delivery object with a stable ID, name,
  description, owner, status, date, dependencies, and product metadata when known.
- Make patches sparse. Omitted entities and properties mean no operation; `unset` explicitly
  clears a property; `change_type: removed` explicitly removes an entity.
- Use `change_type: added` or `changed` as an assertion only when detecting invalid reorderings is
  useful. Otherwise let replay derive add versus modify from entity existence.
- Preserve containment: systems contain applications, applications contain components, and every
  interface or relationship endpoint must exist at its roadmap order.
- Give interfaces stable IDs, clear names, direction, type, technology, and provider/consumer
  semantics. Model meaningful dependencies rather than drawing anonymous arrows.
- Number roadmap items with unique contiguous orders starting at 1. Treat the base as implicit
  order 0. Record `depends_on`; never silently reorder authored delivery intent.
- Use extension metadata or `properties` for domain facts, but do not hide canonical behavior in
  free text. Keep architectural decisions and detailed trade-offs in ADRs and reference the same
  stable architecture IDs.
- Store system and change `group` as lists. In Excel, use `[group-one;group-two]`.
- In Excel `properties`, use a JSON object or `name:value` pairs separated by semicolons or
  newlines. Empty values are allowed; duplicate or malformed names are errors.

Use YAML for reviewable, automated workflows and Excel for structured stakeholder authoring. Use
`arch.convert` to cross the boundary because conversion validates semantic equivalence:

```python
arch.convert(
    input_path='architecture/architecture.yaml',
    output_path='architecture/architecture.xlsx',
)
```

## Design views for questions, not decoration

A selection chooses one authored `state` or one `roadmap`. Select a roadmap endpoint with either
`through` or `order`, never both. A roadmap without an endpoint resolves its final order;
`through='base'` and `order=0` select its base.

Use saved view IDs for repeatable documentation and ad hoc dictionaries for one-off analysis:

```python
selections = [
    'target-state',
    {
        'roadmap': 'preferred',
        'through': 'introduce-payment-orchestrator',
        'compare_from': 'base',
        'visibility': 'changes_with_context',
    },
]
```

Use selection fields deliberately:

- Use `compare_from` to explain cumulative change from a known origin.
- Use `focus` to highlight contributing changes without changing the resolved endpoint.
- Use `browse_by: system` for structure and ownership; use `browse_by: change` for delivery impact.
- Use `system_set` to union systems, system groups, impacted changes, change groups, and tags.
- Use `interface_depth` for recursive interface-hop expansion and `level` for only System,
  Application, or Component. Boundary interfaces are listed without importing the outside system.
- Use `color_by` to choose change status, integration type, or tag independently of topology.
- Use `subject` and `projection` to narrow a view without creating a second model.
- Use `visibility: changes_with_context` for change reviews, `changes_only` for terse deltas, and
  `all` for complete state communication.
- Use `include_future` only with a roadmap when future context is explicitly required.
- Use `diagram` and `theme` as presentation choices; do not encode output format in a saved view.

Create a small, purposeful view set for each solution: current/base context, target context, a
base-to-target comparison, focused views for major changes, and dynamic flows for critical user or
integration journeys. Avoid a combinatorial catalog of nearly identical views.

Keep authored LikeC4 `.c4` files view-only. Use them for static projections, dynamic interactions,
layout, notes, and sequence variants; never declare a second logical `model`, `specification`, or
`deployment`. Treat local PlantUML, Mermaid, SVG, PDF, or HTML attachments as presentation-only,
not as canonical architecture data.

Use workspace-relative local paths for every diagram source. External attachments accept `.puml`,
`.plantuml`, `.mmd`, `.mermaid`, `.svg`, `.pdf`, and `.html`; each file must be at most 10 MiB and
distinct embedded content must remain within the 25 MiB report budget. SVG and HTML must contain
no active or remote markup. Select a diagram through the saved/ad hoc `diagram` field when it
should open by default; changing the explorer's **Diagram view** does not change solution context.

## Validate and inspect diagnostics

Run validation as the publication gate:

```python
result = arch.validate(
    input_path='architecture/architecture.yaml',
    roadmaps=['preferred'],
    views=['target-state'],
)
```

Every operation returns a common envelope. Check all of the following instead of relying only on
tool-call completion:

- Require `result['ok']` and, for validation, `result['valid']`.
- Read every `issues.errors` entry and fix it at its reported YAML path or Excel sheet/row/column.
- Review `issues.warnings` even when the operation succeeds; warnings expose cascades, fidelity
  differences, order sensitivity, and other material context.
- Reconcile intent with `summary`, `selections`, `artifacts`, and `data`.
- Preserve diagnostic codes and source locations in review notes so fixes remain traceable.

Validate the complete workspace before filtering to a roadmap or view. Use filtered validation
only for faster follow-up checks. Validation covers the same schema, replay, selection, LikeC4,
theme, icon, attachment, and exporter paths used for publication.

Keep all assets local and contained. Place sanitized SVG icons under `assets/icons/` and reference
them with `@icons/...`; place attachments under workspace assets. Do not use remote URLs, path
traversal, missing files, or unsafe markup.

## Prove states and changes

Materialize explicit endpoints before design reviews, baselines, or comparisons:

```python
arch.resolve(
    input_path='architecture/architecture.yaml',
    output_path='generated/target.yaml',
    roadmap='preferred',
    through='introduce-payment-orchestrator',
    output_state_id='payments-target',
)
```

Use `state` instead of `roadmap` only for an authored complete state. Do not combine `state` with
`through`, `order`, `focus`, or `include_future`. Prefer explicit selectors and
`output_state_id` in repeatable workflows instead of relying on defaults.

Compare two files that each contain exactly one complete state:

```python
arch.diff(
    base_path='generated/base.yaml',
    target_path='generated/target.yaml',
    output_path='generated/target-change.yaml',
    change_id='derive-payments-target',
)
```

Resolve both endpoints first when comparing roadmap orders. Omit `output_path` for a report-only
diff. Supply an explicit `change_id` whenever materializing a replayable derived change; do not
derive identity from a filename.

## Publish and hand off safely

Generate the self-contained offline explorer for interactive architecture review:

```python
arch.generate(
    input_path='architecture/architecture.yaml',
    output_path='generated/explorer',
    selections=['target-state'],
)
```

When `selections` is omitted, generation starts from the configured default selection, embeds
validated roadmap snapshots and selection indexes, and lays out requested system-set projections
locally. Pass selections explicitly for a bounded review artifact.

Export the same normalized selections for documents and interchange:

```python
arch.export(
    input_path='architecture/architecture.yaml',
    output_path='generated/exports',
    formats=['svg', 'drawio', 'likec4', 'yaml', 'excel'],
    selections=['target-state'],
    drawio_mode='per-view',
)
```

Use only supported formats: `svg`, `drawio`, `likec4`, `yaml`, and `excel`. Use
`drawio_mode='multi-tab'` for one editable file containing multiple selected views. Enable
`continue_on_error=True` only when partial output is acceptable, then require `partial`, artifact
statuses, and errors to be reported accurately.

Write explorers and exports to dedicated generated directories. Let manifests reuse unchanged
artifacts and remove stale tool-owned artifacts. Keep `force=False`; use `force=True` only after
verifying the destination and explicitly accepting replacement of user-owned content. Never edit
generated artifacts as the source of truth.

Create a deterministic offline handoff last:

```python
arch.bundle(
    input_path='architecture',
    output_path='generated/payments-architecture.zip',
    include_generated=False,
)
```

Keep `include_generated=False` for a lean reproducible source bundle. Enable it only when the
recipient needs manifest-owned generated outputs; arbitrary unowned files are not included as
generated artifacts. `include_generated=True` considers only files listed by `manifest.json` or
`.onetool/manifest.json` at the workspace root, so inspect that manifest before bundling.

## Review solution-architecture quality

Before handing off, verify that the documentation:

- States scope, audience, baseline, target endpoint, and roadmap assumptions.
- Uses one canonical logical model across explorer, diagrams, tables, and exports.
- Names systems by responsibility and applications/components by deployable or meaningful runtime
  responsibility, not organizational buzzwords.
- Captures users, boundaries, containment, interfaces, direction, ownership, technology, and
  lifecycle status at the level needed for the decision.
- Separates current facts, proposed changes, delivery order, and presentation concerns.
- Shows critical dynamic journeys and failure-sensitive integrations, not only static boxes.
- Connects important choices to ADRs, constraints, risks, security/privacy concerns, operational
  qualities, and unresolved questions outside the model where deeper prose is required.
- Provides current, target, comparison, and focused change views without duplicating model data.
- Validates cleanly, acknowledges warnings and export fidelity limits, and remains reproducible
  offline from stable IDs and local assets.
