# File formats

Status: active design grill. Settle Architecture authoring formats before
implementing the agreed schema changes. Report Definition and generated output
details remain deferred to the Report session.

## Responsibility

File formats encode domain contracts. They do not define domain meaning.

```text
Authoring formats -> Architecture or Report Definition
Runtime data      -> resolved internal representation
Output formats    -> generated Report artifacts
```

The same Architecture semantics must survive round trips even when YAML and
Excel use different physical layouts.

## Grill order

Resolve these areas one at a time:

1. Whether YAML and Excel are equal authoring formats or one is canonical.
2. Single-file versus multi-file Architecture input.
3. The YAML envelope for Current State, Changes, and Roadmaps.
4. The Excel workbook and sheet model.
5. IDs, blanks, lists, properties, dates, and `unset` encoding.
6. Roadmap ordering in each format.
7. Cross-format equivalence and round-trip guarantees.
8. Validation errors and source locations.
9. The boundary between Architecture files and Report Definition files.
10. Generated HTML and other output packaging.

## Architecture input

Planned authoring formats:

- YAML
- Excel

Confirmed cross-format rules:

- Every Change patch explicitly supplies `change_type`.
- An omitted YAML field means unchanged in a Change.
- A blank Excel field cell means unchanged in a Change.
- `unset: [field]` explicitly clears optional values in both formats.
- `expected` is not part of the starter contract.
- YAML Roadmap Change list position defines order.
- Excel may use a sequence column to construct the same ordered list.
- Different physical layouts must normalise to the same Architecture model.

The exact YAML envelope and Excel sheets or tables remain open. In particular,
the final representation of the one authored Current State is not settled.

## Report Definition input

The saved Report Definition format is not settled. It should encode Report
selection and configuration only. It must not duplicate the resolved
Architecture or contain generated runtime data.

Possible YAML, JSON, and embedded-workspace representations should be evaluated
after the Report Definition contract is known.

## Generated output

HTML is the expected first Report output. The target is a self-contained offline
Report that packages immutable Architecture data and derives tables and diagrams
at runtime.

Other outputs remain to be decided. Candidates include SVG, PNG, PDF, JSON data,
and printable or portable bundles. They should not be added until a clear use
case defines whether the output is a complete Report, one Diagram, or exported
Architecture data.

## Separation rules

- Architecture authoring files do not contain Report runtime state.
- Report Definitions do not contain generated diagram projections.
- Saved diagram placement, if adopted, belongs to Report Definition or a
  Report-owned companion artifact.
- Generated outputs do not become Architecture source.
- Input and output format choices do not add peer domain concepts beside
  Architecture and Report.

## Questions for the format session

1. What is the canonical YAML envelope for the single Current State, Changes,
   and Roadmaps?
2. Which Excel sheets and columns represent the same schema?
3. How are ordered Roadmap Change references represented in Excel?
4. Where do Report Definitions live?
5. What must a self-contained HTML Report package?
6. Which additional export formats are required?
7. What round-trip and cross-format equivalence guarantees are required?
