# Architecture Pack v2

Status: planning documents. These files record the agreed direction but do not
change the implemented contract.

## Parts

Architecture Pack v2 is split by responsibility:

| Part | Owns | Does not own |
| --- | --- | --- |
| [Architecture schema](schema.md) | Architecture entities, Current State, Changes, Roadmaps, validation, and State resolution | Report scope, diagrams, layout, or output rendering |
| [Report](report.md) | Architecture selection, report scope, tables, diagrams, saved definitions, and runtime interaction | Architecture truth or mutation |
| [File formats](file-formats.md) | Canonical Architecture YAML and its Excel import and export mapping | Domain meaning, Report Definitions, or generated Report outputs |
| [Architecture schema decisions](grill/schema-grill.md) | Schema interview history, rejected alternatives, and research | The concise working contract |
| [File-format decisions](grill/file-formats-grill.md) | YAML and Excel interview history and rejected alternatives | The concise working contract |

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

The Architecture schema and its YAML and Excel formats are agreed and ready for
implementation planning. Report design remains paused for a separate session.

No public `View` concept crosses these parts. A Report Definition is the saved
selection and configuration. A Diagram is one visual inside a Report. A
Projection is an internal set of nodes and connections prepared for a Diagram.
