# Architecture Pack v2

Status: planning documents. These files record the agreed direction but do not
change the implemented contract.

## Parts

Architecture Pack v2 is split by responsibility:

| Part | Owns | Does not own |
| --- | --- | --- |
| [Architecture schema](schema.md) | Architecture entities, Current State, Changes, Roadmaps, validation, and State resolution | Report scope, diagrams, layout, or output rendering |
| [Report](report.md) | Architecture selection, report scope, tables, diagrams, saved definitions, and runtime interaction | Architecture truth or mutation |
| [File formats](file-formats.md) | YAML and Excel input mappings, saved-definition files, and generated output formats | Domain meaning |
| [Decision trail](grill.md) | The interview history, rejected alternatives, research, and unresolved questions | The concise working contract |

Implementation planning should remain separate until these contracts are ready
to enter the OpenSpec workflow.

## Pack boundary

The pack has two domain concepts:

1. **Architecture** owns the organisation's architecture data and its evolution
   from Current State to Target State.
2. **Report** selects and presents that architecture without changing it.

File formats are adapters around those concepts. They are not a third domain
model.

```text
YAML / Excel
    -> Architecture schema
    -> resolve Current State + Changes through a Roadmap
    -> selected State
    -> Report Definition
    -> Report runtime
    -> HTML and other outputs
```

## Current status

The Architecture schema direction is written up and ready for a focused schema
review. Report design is intentionally paused for a separate session. File
formats contain only decisions forced by the domain work so far.

No public `View` concept crosses these parts. A Report Definition is the saved
selection and configuration. A Diagram is one visual inside a Report. A
Projection is an internal set of nodes and connections prepared for a Diagram.
