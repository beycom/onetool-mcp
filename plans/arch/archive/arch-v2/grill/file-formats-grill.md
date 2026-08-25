# Architecture file-format grill

Status: interview complete. Shared understanding confirmed 2026-08-22.

This is the decision trail for
[Architecture file formats](../file-formats.md). The format document is the
working contract when wording here becomes stale.

## Scope

This grill settled the canonical Architecture YAML and its Excel import and
export mapping. Report Definitions and generated Report outputs belong to the
Report grill.

## Source authority

### YAML is canonical

Excel remains important because architects can edit it easily and organisations
commonly share workbooks through SharePoint. It is still an interchange format,
not a second source of truth.

The workflow is:

```text
Excel or SharePoint
    -> import and validate
    -> replace canonical YAML atomically
    -> resolve and report from YAML
    -> export a new workbook when needed
```

Import replaces the complete Architecture. It does not merge rows into existing
YAML. Failed validation leaves the current YAML untouched. Export does not
rewrite the imported workbook because that would create an accidental promise
to preserve formulas, comments, unsupported sheets, and presentation details.

Runtime Architecture operations accept YAML only. Excel must pass through
import first.

### One Architecture file

One Architecture uses one YAML file. Splitting Current State, Changes, or
Roadmaps across files was rejected. Includes would need precedence, ordering,
atomicity, and cross-file error rules without solving a current requirement.

Report Definitions may be separate files, but their format is outside this
grill.

### No revision token

A content hash on exported workbooks was considered as protection against stale
SharePoint copies. It was rejected for the first version. Import is an explicit
full replacement and does not perform conflict detection.

## YAML envelope

The agreed root is direct:

```yaml
schema_version: 2
current_state:
  systems: []
  subsystems: []
  components: []
  users: []
  interfaces: []
  relationships: []
changes: []
roadmaps: []
```

An `architecture` wrapper was rejected because the file cannot contain several
Architectures. The old `states: [{id: current}]` shape was rejected because the
domain has exactly one authored Current State. Derived States have no public
IDs.

All four root keys and all six Current State collection keys are required. The
collections may be empty, including an entirely empty Current State for a
greenfield Architecture. Current State has no ID or metadata of its own.

The format accepts `.yaml` and `.yml`, then generates `.yaml`. It uses YAML 1.2.
Anchors, aliases, merge keys, duplicate keys, nulls, unknown fields, and empty
strings are invalid.

`schema_version` accepts `2` and `"2"`, then serialises as integer `2`.

## Domain fields

Every domain kind has `id`, optional `description`, optional `tags`, and optional
`properties`. System, Subsystem, Component, User, and Interface require `name`.
Relationship has required `action` instead of `name`.

Subsystem requires `system`. Component requires `subsystem`. Interface requires
`provider` and `consumer`; its two direction fields default to `unspecified`.
Relationship requires `source`, `action`, and `target`.

Technology was considered as a dedicated field. It remains an optional
property. Interface type and User kind follow the same rule because none of
these fields changes validation or resolution. Generic group, notes, icon, and
style fields were removed from the Architecture starter contract.

## Changes and clearing

Every Change has `id`, `name`, optional `description`, and at least one patch.
Unreferenced Changes are valid so an architect can prepare work before assigning
it to a scenario.

Every patch declares `change_type`. Enum input ignores case and canonical output
uses lowercase.

### Per-field `unset`

The first design used `unset: [field]`. The interview then considered YAML null
and Excel text `null`. Null was rejected because it blurred absent input, empty
values, and patch instructions.

The final design places `unset` in the value being cleared:

```yaml
description: unset
tags: unset
properties:
  owner: unset
```

`clear` was considered and rejected. `unset` describes removing an optional
field or property, while `clear` may sound like setting an empty string.

`unset` is case-insensitive on input and lowercase on output. It works only in a
`changed` patch. It removes a description, empties tags, or removes one property.
It cannot clear required values or the whole `properties` map. Authors use
`unspecified` to reset an Interface direction.

Removed patch rows contain only Change ID, Change type, and entity ID. Added
patches cannot contain `unset` because no previous value exists.

### Sparse properties

Properties are flat. Their values are strings or ordered lists of strings.
Nested properties were rejected because they do not map to ordinary Excel
columns. Numbers, booleans, and dates are text after conversion.

A changed property map is sparse. A supplied value replaces that property, an
`unset` value removes it, and omission preserves its previous value. The whole
map cannot be replaced or cleared in one operation.

Property names compare without case sensitivity and preserve their first
declared spelling. Property-list values remain opaque. Their order, casing, and
duplicates are preserved.

## IDs, tags, and strings

IDs allow ASCII letters, digits, `.`, `_`, and `-`, with no whitespace. They may
start with a digit. Matching ignores case, but declarations keep their spelling.
`SAP-1`, `sap-1`, and `Sap-1` therefore identify the same object. A second
case-equivalent declaration is a duplicate.

Tags follow the same case-insensitive matching and spelling-preservation rule.
Case-equivalent duplicates on one entity are invalid. Tag order is preserved.

All strings are trimmed at their outer edges and must remain nonblank. Lists
contain strings only. This avoids type disagreement between YAML lists and
Excel's compact list cells.

## Excel workbook

The first version supports `.xlsx`, not `.xlsm` or CSV. A workbook has these
nine sheets:

1. `Architecture`
2. `Systems`
3. `Subsystems`
4. `Components`
5. `Users`
6. `Interfaces`
7. `Relationships`
8. `Changes`
9. `Roadmaps`

Missing and unknown sheets are errors. Generated workbooks use tables, filters,
frozen headers, and dropdowns, but import does not require those presentation
features. Formulas are invalid input.

`Architecture` has one `schema_version` row. It has no hash, Architecture ID, or
embedded YAML.

### Combined domain sheets

Current State rows and Change patch rows share one sheet per domain kind. A
blank `change` means Current State. Patch rows require `change` and
`change_type`. A design with separate Current State and patch sheets was
rejected because it would double the sheet count.

The six domain sheets have fixed reserved headers. They correspond directly to
the fields agreed in the schema. All reserved headers remain present, even when
the sheet has no rows or the optional columns are empty.

Any non-reserved domain header is a property name. A `property.` prefix and a
JSON properties cell were rejected in favour of ordinary columns such as
`owner` and `lifecycle`. This is easier to edit and filter. It also means a typo
such as `descripton` becomes a valid property. That tradeoff was accepted.

Reserved-name collisions and duplicate normalised headers are errors. A
populated cell beneath a blank header is also an error. Any nonblank domain row
requires an ID.

### Changes and Roadmaps sheets

`Changes` has `id`, `name`, and `description`. Each patch and Roadmap reference
must resolve to a declared Change. The importer never invents Change metadata.

`Roadmaps` has `roadmap` and `change`. An explicit sequence column was rejected.
Excel row order carries the same meaning as YAML list order. Each Roadmap uses
one contiguous block of rows, contains at least one Change, and cannot repeat a
Change. Empty Roadmaps were rejected because Current State already has its own
selector.

### Excel parsing

Header comparison ignores case and treats spaces, hyphens, and underscores as
equivalent. Exports use lowercase `snake_case` for reserved headers. Sheet names
ignore case but otherwise use the nine exact names.

Excel lists use semicolons:

```text
[tag1;tag2;tag3]
```

YAML keeps its native comma syntax. Making YAML accept semicolons was rejected
because standard YAML reads that form as one list item. A bare Excel value is
accepted for a known one-item list field. List items cannot contain semicolons,
brackets, or line breaks.

Excel scalar property cells convert to strings. Whole numbers use decimal text,
booleans use `true` or `false`, dates use `YYYY-MM-DD`, and date-times use ISO
8601. Export writes properties as text.

## Ordering and round trips

YAML Roadmap list order and Excel Roadmap row order are semantic. Other authored
collection, patch, and list orders are preserved.

Excel export writes Current State rows first, then patch rows in Change order.
It writes reserved columns first and sorts property columns without case
sensitivity.

Round trips guarantee Architecture model equality, not source presentation.
YAML comments, quoting, whitespace, and key layout are not preserved. Excel
styles, comments, widths, filters, formulas, and unrelated sheets are not
preserved. Export creates a new workbook.

## Errors and provenance

YAML errors identify file, line, column, and data path. Excel errors identify
workbook, sheet, cell, and field or property. Duplicate and reference errors
include all relevant declaration locations. Import collects independent errors
when parsing can continue.

Excel locations are not written into canonical YAML. After import, YAML is the
source and later diagnostics point to it.

## Deferred decisions

This grill does not choose:

- Report Definition structure or location;
- generated HTML packaging;
- SVG, PNG, PDF, or other Report outputs;
- SharePoint transport or authentication.

Those decisions do not block Architecture schema implementation.
