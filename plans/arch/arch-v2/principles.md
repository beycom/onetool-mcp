# Architecture Pack v2 principles

Architecture Pack v2 is an architecture truth-and-change engine that produces
trustworthy reports. Use these principles when a design decision becomes lost in
schema, format, or presentation details.

## 1. Keep truth, presentation, and file formats separate

Architecture owns entities, connections, Changes, Roadmaps, and resolved States.
Report selects and presents Architecture data without changing it. YAML and Excel
are adapters around those concepts, not additional domain models.

If a field exists only for layout, filtering, interaction, or display, it does
not belong in Architecture.

See [Architecture Pack v2](index.md#pack-boundary) and
[Report](report.md#responsibility).

## 2. Maintain one canonical architecture truth

One Architecture has one authoritative YAML file. Excel is an authoring and
exchange format that imports into canonical YAML. A valid import replaces the
file atomically, while a failed import leaves it unchanged. Runtime operations
consume Architecture YAML rather than working directly from Excel.

Do not introduce parallel sources of truth, partial-file merging, or
format-specific domain behaviour.

See [Architecture file formats](file-formats.md#responsibility).

## 3. Author the present and the Changes, then derive the future

Authors define one complete Current State and sparse, explicit Changes. Roadmaps
order those Changes. The resolver replays them to produce complete intermediate
States and a Target State.

Omission in a Change means unchanged. Removal and field clearing are explicit.
Each Change applies atomically. Do not require repeated snapshots or infer
author intent from missing data.

See [Architecture schema](schema.md#current-state-change-and-roadmap).

## 4. Be strict about structure and restrained about meaning

The schema enforces stable IDs, fixed `System -> Subsystem -> Component`
containment, singular ownership, valid endpoints, and the distinction between a
realised Interface and a semantic Relationship. It does not judge whether an
architect chose the ideal abstraction.

Keep open-ended metadata in `properties`. Add a dedicated schema field only when
validation, resolution, or another concrete Architecture behaviour needs to
understand it.

See [Architecture schema](schema.md#entity-structure),
[Interface](schema.md#interface), and [Relationship](schema.md#relationship).

## 5. Make every Report one consistent projection of Architecture truth

A Report selects a State and one primary System scope. Interfaces may expand that
scope by System hops. Every table, count, and Diagram derives from the same
Report scope.

A Diagram may narrow its Projection but cannot silently widen the Report.
Boundary Interfaces remain visible without adding excluded Systems to scope.
Changing the displayed Interface aspect changes presentation, not State or scope.

See [Report](report.md#primary-system-scope),
[Scope-boundary Interfaces](report.md#scope-boundary-interfaces), and
[Interface aspect](report.md#interface-aspect).

## Delivery order

Build the canonical model and validation first, followed by Change replay and
Roadmap resolution. Build Report behaviour on the resulting Architecture
boundary. The Architecture schema and file formats are ready for implementation
planning, while the Report contract still requires its own design session.
