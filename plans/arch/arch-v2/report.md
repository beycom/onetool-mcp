# Report

Status: handoff for a separate design session. This document records only the
Report decisions already made and the questions still open.

## Responsibility

Report selects and presents Architecture data. It does not own or mutate the
Architecture, apply Changes, or redefine entity and connection meaning.

The packaged Architecture data remains unchanged while a Report runs. Reports,
tables, diagrams, and runtime projections are derived on demand. The pack does
not need to pre-create every possible Report.

## Terms

- **Report Definition** is a saved recipe that selects Architecture data and
  configures Report content.
- **Report** is the generated experience produced from a Report Definition.
- **Diagram** is one visual inside a Report.
- **Projection** is an internal subset of nodes and connections prepared for a
  Diagram.

`View` is not a public synonym for Report. The current top-level `views` concept
will be removed. Useful selection and configuration fields move into Report
Definition.

## State selection

Report consumes the State selectors defined by Architecture:

```yaml
state: current
```

```yaml
roadmap: preferred
through: phase-1
```

```yaml
roadmap: preferred
```

These select Current State, an intermediate State, and Target State. Report does
not use generated State IDs or numeric Roadmap positions.

Whether a Report may also select a comparison origin remains open. The likely
model is one selected State plus an optional comparison origin using the same
selector grammar. That would support snapshot and comparison Reports without
separate Report types.

## Primary system scope

One Report Definition has one primary Architecture scope.

- Scope starts from one or more Selected systems.
- Most Reports will start from one or two Systems.
- `system_hops` expands scope through Interfaces.
- `system_hops: 0` means Selected systems only.
- Traversal is undirected. Provider, consumer, call direction, and data flow do
  not restrict it.
- Parallel Interfaces between the same Systems count as one hop.
- Interfaces within one System do not count as a System hop.
- Relationships never expand scope.
- Each included System retains whether it was selected or its shortest hop
  distance from a Selected system.

Use these terms:

- **Selected systems** for the explicitly chosen Systems.
- **Scope expansion** for the operation.
- **System hops** for the configured distance.
- **Report scope** for the resulting set.

`interface_depth` is removed without an alias. "Blast radius" is not a public
term.

Every Report table, count, and generated Diagram derives from Report scope. A
Diagram may show a smaller Projection but cannot silently widen the Report.

## Scope-boundary Interfaces

An Interface whose endpoint Systems are both in Report scope is an Internal
interface. An Interface with exactly one endpoint System in scope is a Boundary
interface.

Boundary Interfaces remain in the Interface table. A Diagram shows the excluded
endpoint as a compact labelled System stub. The stub does not add that System to
Report scope, counts, other tables, or detailed Diagrams.

## Interface aspect

Report may display three independent aspects of the same Interfaces:

- **Ownership**, derived from provider to consumer;
- **Call direction**, read from `call_direction`;
- **Data flow**, read from `data_flow`.

Switching aspect changes arrows, labels, legend, and table emphasis. It does not
change State selection, Report scope, or Diagram membership. An unspecified
direction renders neutrally rather than falling back to ownership.

## Initial Report family

The original ideas identify these areas for the Report session:

- Report Definition configuration;
- report runtime;
- tables;
- diagrams;
- saved Report Definitions;
- generated outputs.

Diagram behavior to review includes level, pan and zoom, additional details,
saved coordinates, generated diagrams, dynamic diagrams, and additional
authored diagrams. These are not yet settled concepts or schema fields.

Saved-report ideas include reusable System sets and hop-based selection. Their
relationship to Report Definition still needs clarification.

## Questions for the Report session

Work through these in order:

1. Does one Report select one State plus an optional comparison origin?
2. What exact resolved data contract crosses from Architecture into Report?
3. What is the minimal Report Definition schema?
4. Which tables are always present and which are configured?
5. What belongs in the Diagram catalogue versus a Report Definition?
6. What do generated, dynamic, and additional Diagram mean?
7. Which choices persist and which runtime interactions are transient?
8. Does saved placement store absolute coordinates, hints, or user intent?
9. Are System sets first-class reusable selectors or only Report fields?
10. What Report outputs are required after HTML?

## Explicitly deferred

Do not settle Report questions by adding fields to Architecture. Delivery dates,
owners, groups, tags, and other metadata return to the Architecture schema only
when the Report session identifies a concrete need and clear ownership.

