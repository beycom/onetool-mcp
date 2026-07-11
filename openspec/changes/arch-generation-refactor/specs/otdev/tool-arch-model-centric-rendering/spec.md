# tool-arch-model-centric-rendering Delta

## MODIFIED Requirements

### Requirement: Regenerated solution output
`arch.generate` SHALL fully own the solution output directory and SHALL update it
incrementally: output files are rewritten only when their content changes, diagram renders
are skipped when their inputs are unchanged, stale files are removed after a successful run,
and `force=True` restores full regeneration. Existing outputs SHALL NOT be bulk-deleted
before new outputs are produced.

#### Scenario: Stale outputs removed
- **WHEN** generation completes successfully into a solution directory containing files from
  a previous run that are not part of the current model's output set
- **THEN** those stale files SHALL be removed so the directory reflects only the current model

#### Scenario: Unchanged diagram render reused
- **WHEN** generation runs and a system or project diagram's generated `.d2` source is
  identical to the file from the previous run, its `.svg` output exists, and the svg's
  embedded draw.io state matches the run's `drawio_export` setting
- **THEN** the render engine SHALL NOT be re-invoked for that diagram
- **AND** the existing `.svg` SHALL be reused in the generated report pages

#### Scenario: Changed diagram re-rendered
- **WHEN** generation runs after a model change that alters a diagram's generated `.d2` source
- **THEN** that diagram SHALL be re-rendered through the configured engine and its outputs
  rewritten

#### Scenario: Forced full regeneration
- **WHEN** `arch.generate(..., force=True)` is called
- **THEN** every output file SHALL be rewritten and every diagram SHALL be re-rendered,
  regardless of unchanged inputs

#### Scenario: Render reuse reported
- **WHEN** generation completes successfully
- **THEN** the result `summary.renders` SHALL report the number of executed and skipped
  engine renders

#### Scenario: No destructive pre-clean on failure
- **WHEN** generation fails partway through a run
- **THEN** outputs from the previous successful run SHALL NOT have been bulk-deleted at the
  start of the failed run
