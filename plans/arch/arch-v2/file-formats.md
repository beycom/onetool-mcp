# Architecture file formats

Status: Architecture YAML and Excel contract agreed. Ready for schema
implementation. Report Definition and generated-output formats remain deferred
to the Report grill.

## Responsibility

YAML is the canonical Architecture format. Excel is an authoring and exchange
format that imports into and exports from canonical YAML.

```text
Excel or SharePoint
    -> import and validate
    -> canonical Architecture YAML
    -> resolve and report
    -> export a new Excel workbook
```

One Architecture has one authoritative YAML file. Import replaces that file as
one atomic operation. A failed import leaves the existing YAML unchanged. The
importer does not merge rows into an existing Architecture.

Resolution and report generation accept Architecture YAML, not Excel. An Excel
workbook must pass through import first. Export always creates a new workbook;
it does not update the imported workbook in place.

## Canonical YAML

Architecture input accepts `.yaml` and `.yml`. Generated files use `.yaml`,
UTF-8, and YAML 1.2.

One file contains one Architecture with four required root keys:

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

The root has no `architecture` wrapper. `current_state` is singular and has no
ID, name, description, or properties. Its six collection keys are required,
even when empty. An empty Current State is valid. `changes` and `roadmaps` are
also required and may be empty.

`schema_version` accepts the integer `2` or the string `"2"`. Generated YAML
writes the integer. Other values are invalid.

### Entity fields

All six domain kinds have:

- required `id`;
- optional `description`;
- optional `tags`;
- optional `properties`.

System, Subsystem, Component, User, and Interface require `name`. Relationship
uses required `action` instead of `name`.

Kind-specific fields are:

| Kind | Fields |
| --- | --- |
| System | no additional fields |
| Subsystem | required `system` parent reference |
| Component | required `subsystem` parent reference |
| User | no additional fields |
| Interface | required `provider` and `consumer`; `call_direction` and `data_flow` default to `unspecified` |
| Relationship | required `source`, `action`, and `target` |

`technology`, Interface `type`, and User `kind` are properties when needed.
Generic `group`, `notes`, `icon`, and `style` fields are not part of the
Architecture contract.

### Changes

Each Change has required `id`, required `name`, optional `description`, and a
required `patches` mapping. The mapping groups patches under `systems`,
`subsystems`, `components`, `users`, `interfaces`, and `relationships`. Empty
groups may be omitted, but every Change must contain at least one patch.

A Change need not belong to a Roadmap. This permits authored work before a
scenario adopts it.

Every patch requires `id` and `change_type`. The accepted Change types are
`added`, `changed`, and `removed`. Input matching ignores case; generated YAML
writes lowercase values.

Omitting a field from a `changed` patch leaves its current value unchanged.
The scalar marker `unset` clears a supported field:

```yaml
changes:
  - id: phase-1
    name: Phase 1
    patches:
      systems:
        - id: payments
          change_type: changed
          description: unset
          tags: unset
          properties:
            owner: unset
            lifecycle: active
```

`unset` matching ignores case and accepts quoted or unquoted input. Generated
YAML writes lowercase `unset`. It is valid only in `changed` patches:

- `description: unset` removes the description;
- `tags: unset` produces an empty tag list;
- `properties.<name>: unset` removes that property.

The `properties` mapping itself cannot be unset. Required IDs, names, parents,
endpoints, Relationship actions, and Interface direction fields cannot be
unset. Set an Interface direction to `unspecified` explicitly. `added` and
`removed` patches cannot contain `unset`.

YAML null is invalid throughout the Architecture format. Empty strings are also
invalid. Authors omit optional Current State and addition fields, omit unchanged
patch fields, and use `unset` only for an explicit removal.

### Roadmaps

YAML list position defines Change order:

```yaml
roadmaps:
  - id: preferred
    changes:
      - phase-1
      - phase-2
```

A Roadmap must contain at least one Change. Each reference must resolve to a
declared Change, and one Change may appear only once in a Roadmap. Different
Roadmaps may reference the same Change.

## IDs and text

IDs are trimmed nonblank strings containing only ASCII letters, digits, `.`,
`_`, and `-`. They may start with a digit. YAML authors must quote an ID that
YAML would otherwise parse as a number. Excel whole-number ID cells convert to
decimal text. Booleans and decimal-number cells are invalid IDs.

ID matching ignores case but preserves the spelling of the declaration. For
example, `SAP-1`, `sap-1`, and `Sap-1` resolve to the same identity. A second
declaration that differs only by case is a duplicate. Generated references use
the declaration's spelling.

All strings are trimmed at their outer boundaries and must remain nonblank.
Descriptions may contain internal spaces and line breaks.

Enum input ignores case. Canonical output writes:

- `added`, `changed`, and `removed`;
- `provider_to_consumer`;
- `consumer_to_provider`;
- `bidirectional`;
- `unspecified`.

## Tags and properties

Tags are ordered nonblank strings. Matching ignores case while display retains
the first declared spelling. Case-equivalent duplicates on one entity are
invalid.

Properties form a flat map. Property names are nonblank, compare without case
sensitivity, and retain the first declared spelling. Spaces, hyphens, and
underscores compare as equivalent in property names. A property name cannot
normalise to a reserved domain column for its entity kind.

A property value is either a nonblank string or an ordered list of nonblank
strings. Nested maps, nested lists, nulls, numbers, and booleans are invalid in
canonical YAML properties. The scalar string `unset` is reserved and cannot be
stored as a field or property value.

Property-list order, casing, and duplicates are preserved. The schema does not
assign meaning to arbitrary property values. List items in either format cannot
contain semicolons, square brackets, or line breaks.

A `changed` patch applies `properties` as a sparse map patch. Supplied string or
list values replace those property values, supplied `unset` markers remove
those keys, and omitted keys remain unchanged.

YAML uses native comma-separated lists:

```yaml
tags: [core, payments]
properties:
  owner: Payments Team
  regions: [ap-southeast-2, us-east-1]
```

Generated YAML quotes strings that YAML would otherwise parse as another scalar
type.

## Excel workbook

Excel import and export support `.xlsx` only. A workbook contains exactly these
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

Sheet-name matching ignores case but otherwise requires these names. Missing or
unknown sheets are errors. Empty sheets retain their header row.

Generated workbooks use Excel tables, filters, frozen headers, and enum
dropdowns. Imports depend only on sheet names, headers, and cell values. A
manually created workbook does not need the generated presentation features.

Formulas are invalid input. Import reads authored cell values only.

### Architecture sheet

`Architecture` contains one header and one data row:

| schema_version |
| --- |
| 2 |

Additional populated rows are invalid. The workbook carries no source revision,
Architecture ID, or embedded YAML.

### Domain sheets

Each domain sheet contains Current State rows and Change patches in one table.
The reserved columns are:

| Sheet | Reserved columns |
| --- | --- |
| `Systems` | `change`, `change_type`, `id`, `name`, `description`, `tags` |
| `Subsystems` | `change`, `change_type`, `id`, `name`, `system`, `description`, `tags` |
| `Components` | `change`, `change_type`, `id`, `name`, `subsystem`, `description`, `tags` |
| `Users` | `change`, `change_type`, `id`, `name`, `description`, `tags` |
| `Interfaces` | `change`, `change_type`, `id`, `name`, `provider`, `consumer`, `call_direction`, `data_flow`, `description`, `tags` |
| `Relationships` | `change`, `change_type`, `id`, `source`, `action`, `target`, `description`, `tags` |

Every reserved column is present, even when empty. Any additional column is a
property whose name is the column header. Property columns that collide with a
reserved header are invalid. This bare-column design means a misspelled reserved
header can become a property; the generated template reduces but cannot remove
that risk.

A blank `change` and `change_type` place a row in Current State. A patch row
requires both values. Blank patch cells mean unchanged. A cell containing
`unset`, with any case and with or without surrounding double quotes, applies
the clearing rules above.

`removed` rows may contain values only in `change`, `change_type`, and `id`.
`added` rows cannot contain `unset`. Every nonblank domain row requires `id`.

### Changes sheet

`Changes` has exactly these reserved columns:

| id | name | description |
| --- | --- | --- |
| phase-1 | Phase 1 | Initial delivery |

Every patch `change` value must match one row on this sheet. The importer does
not create undeclared Changes or derive a missing name from an ID.

### Roadmaps sheet

`Roadmaps` has two reserved columns:

| roadmap | change |
| --- | --- |
| preferred | phase-1 |
| preferred | phase-2 |
| alternate | phase-1 |

Row order within a Roadmap defines Change order. Each Roadmap occupies one
contiguous block. A later repeated block for the same Roadmap ID is invalid.
Every block is nonempty, its Change references resolve, and it cannot repeat a
Change.

### Excel values

An empty cell means absent in Current State and unchanged in a patch. Fully
blank rows and trailing blank columns are ignored. Populated cells below blank
headers are errors.

Header matching ignores case and treats spaces, hyphens, and underscores as
equivalent. Generated headers use lowercase `snake_case`. Duplicate headers
after normalisation are invalid. Property names follow the same comparison
rule.

Excel list syntax uses brackets and semicolons:

```text
[core;payments]
[]
```

A bare value in a known list field, such as `core` in `tags`, becomes a
one-item list. A bare property value is a scalar string; brackets make it a
property list. List items cannot contain semicolons, square brackets, or line
breaks.

Excel property cells convert to canonical text as follows:

| Excel value | Property string |
| --- | --- |
| text | trimmed text |
| whole number | decimal text |
| boolean | `true` or `false` |
| date | `YYYY-MM-DD` |
| date-time | ISO 8601 text |

Generated workbooks write property values as text so Excel does not change
their type.

### Export order

Generated domain sheets write Current State rows first in YAML order. Patch rows
follow in `changes` list order, and each patch group preserves its YAML order.
The `Changes` sheet preserves YAML list order. `Roadmaps` preserves Roadmap list
order and each Roadmap's Change order.

Reserved columns come first. Property columns follow in case-insensitive sorted
order.

## Cross-format guarantees

YAML and Excel normalise to the same Architecture model. Semantic equality
includes IDs, field values, collection order, list order, Changes, patch order,
Roadmaps, and Roadmap order.

`YAML -> Excel -> YAML` preserves that model. It does not preserve comments,
anchors, aliases, quoting, whitespace, or key layout. Anchors, aliases, merge
keys, and duplicate YAML mapping keys are invalid input.

`Excel -> YAML -> Excel` preserves Architecture data. It does not preserve
workbook styles, comments, formulas, widths, filters, or unrelated sheets.
Export writes a new workbook.

Excel paths, sheet names, and cell addresses do not appear in generated YAML.
They belong to the import result and validation errors.

## Validation errors

YAML errors include file, line, column, and data path. Excel errors include
workbook, sheet, cell, and field or property name. Duplicate and broken-reference
errors include every relevant declaration location.

Import collects independent errors in one run when parsing can continue. A
syntax error that prevents parsing may stop validation of that file.

Unknown YAML fields are errors. Open-ended entity metadata belongs under
`properties`. Unknown columns on `Architecture`, `Changes`, and `Roadmaps` are
errors. Additional domain-sheet columns are properties by definition.

## Deferred formats

Report Definition files and generated Report outputs are not part of this
contract. Their envelope, location, packaging, and output types belong to the
Report grill. Architecture authoring files never contain Report runtime state,
diagram projections, or generated layout.
