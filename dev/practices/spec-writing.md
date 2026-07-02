# Spec Writing

This guide is intentionally generic. It should apply across projects. Do not
add project-specific product names, tool names, config keys, directory maps,
test markers, commands, or workflow exceptions to this file. Put those details
in the relevant project's spec index, developer guide, or active change
artifacts.

OpenSpec specs are the current product contract: what the project provides now
to users, operators, clients, integrations, or other systems. They should be
concise enough to review, stable enough to survive implementation changes, and
specific enough to guide future changes.

## What Belongs In Specs

Write requirements for externally meaningful behavior:

- User-facing commands, flags, outputs, errors, and config contracts
- Public APIs, protocol surfaces, tool interfaces, and observable behavior
- Runtime service behavior such as endpoints, auth boundaries, state ownership,
  lifecycle, retention, and failure modes
- Data formats that users, clients, tools, or integrations depend on
- Non-functional product requirements that cut across capabilities, such as
  observability, reliability, privacy, path/storage boundaries, documentation
  availability, accessibility, performance, or security posture

Use the project's `openspec/specs/INDEX.md` naming conventions when present.
If `_nf-*` specs are used, they must describe cross-cutting non-functional
requirements of the product, not development practices.

## What Does Not Belong

Do not use main specs as a dumping ground for implementation plans, repository
process, or team preferences:

- Test plans, coverage goals, test file locations, test markers, fixtures,
  mocks, CI matrices, or regression-check mechanics
- Internal helper names, private classes, module layouts, import paths, library
  choices, or refactor steps, unless the library or file format is itself part
  of the public contract
- Code style, lint rules, docstring style, logging helper conventions, review
  workflow, branch workflow, or release process
- Historical removal notes such as "ensure old X is removed" in main specs
- One-time migration tasks, archive rationale, proposal history, or completed
  task lists
- Project-specific navigation, commands, or directory ownership rules in this
  generic guide

Some of this information is valid elsewhere. Put implementation work in an
active change's `tasks.md`, tradeoffs in `design.md`, and durable development
standards in developer documentation.

## Functional Vs Non-Functional

Functional specs describe capabilities users or integrations can invoke or
observe. Examples: CLI commands, public APIs, tool calls, background services,
UI workflows, config schemas, and persistent data formats.

Non-functional specs describe product qualities or operating constraints that
apply across multiple capabilities. They are still product specs: a user,
operator, client, or integrating system should be able to observe or depend on
the requirement.

Good `_nf-*` examples:

- Observability: runtime event shape, redaction, attribution, diagnostic
  visibility, auditability
- Paths/storage: workspace boundaries, state ownership, retention, backup
  behavior, path resolution semantics
- Documentation: public documentation availability, interface accuracy,
  required privacy/security disclosures
- Reliability/performance: timeout behavior, bounded resource use, retry
  contracts, degradation behavior
- Security/privacy: auth boundaries, secret handling, data exposure limits,
  opt-out requirements

Bad `_nf-*` examples:

- Testing standards, coverage rules, fixture mechanics, CI setup
- Code style, helper APIs, import conventions, docstring format, lint rules
- Repository layout preferences or module ownership rules
- "Every implementation must use library X" unless library X is part of the
  public contract or output format

## Main Specs Vs Delta Specs

Main specs under `openspec/specs/` describe what is built now. They should read
like current truth, not changelog history.

`openspec/changes/` is a work-in-progress area for proposals and active
changes. Delta specs describe how a change intends to update the current truth.
`REMOVED Requirements` is appropriate in delta specs because a change needs to
explain what contract is being deleted.

When archiving a change, merge the final behavior into `openspec/specs/` and
drop obsolete history. If a removed behavior no longer exists, do not keep a
main-spec requirement whose only purpose is to say it is gone. Keep negative
requirements only when the absence is itself a live product boundary, such as
"a read-only token SHALL NOT authorize write operations".

## Scenario Quality

Good scenarios prove the contract from an outside point of view:

- Start from a user action, API call, tool call, request, config, file, or
  observable system state
- State the expected result, output shape, error, persisted state, emitted
  event, or visible side effect
- Include edge cases only when they define supported behavior or a safety
  boundary
- Prefer one clear scenario over several near-duplicates

Avoid scenarios that only assert implementation details:

- "WHEN the helper function is called"
- "THEN this private module is imported"
- "THEN a unit test exists"
- "THEN the code uses a specific library"
- "THEN the implementation follows the style guide"

## Level Of Detail

Specs should be detailed enough to protect product behavior and no more.

Prefer:

- Stable inputs and outputs
- Supported values and validation errors
- Persistence and retention contracts
- Auth, trust, and privacy boundaries
- Observable logging/telemetry outcomes
- User-visible failure and degradation behavior

Avoid:

- Source file paths as requirements
- Internal data structures that can change without affecting users
- One requirement per helper or private method
- Exact wording of non-user-facing logs unless clients parse it
- Exhaustive examples when a compact rule defines the same behavior

For large capabilities, group requirements by user capability or externally
visible workflow rather than by implementation component.

## Bloat Checks

Before adding or syncing a spec, ask:

- Is this a product contract someone can observe or depend on?
- Would this still matter if the implementation changed?
- Is this already covered by a broader requirement?
- Does it belong in a change artifact, developer guide, test, or release notes
  instead?
- Can two or more scenarios be collapsed without losing behavior?
- Is this generic guide the right place, or is the content project-specific?

If the answer is unclear, keep the spec smaller and put extra detail in the
active change's `design.md`, `tasks.md`, or the relevant developer guide.

## Review Checklist

Use this checklist when reviewing specs:

- Requirements describe current product behavior, not implementation history
- Main specs do not contain stale `Removed:` sections or archive rationale
- Negative requirements protect an active product boundary
- Test/process/development guidance is absent from main specs
- `_nf-*` specs describe product qualities, not development practices
- Large specs are grouped by user capability rather than helper/module layout
- Scenarios use `GIVEN`/`WHEN`/`THEN` and remain externally observable
- Generic guidance files do not contain project-specific product details
