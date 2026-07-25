## Context

The standalone `otpack` package exports generic `get_state` and `set_state`
helpers backed by a dedicated YAML module. No production code uses them, while
active tools use `get_project_state_dir` to own their state lifecycle directly.
The generic writer performs an unlocked read-modify-write of a shared document,
so retaining it would require a persistence and concurrency design without a
product consumer.

## Goals / Non-Goals

**Goals:**

- Remove the generic public state API and its implementation as one breaking v3
  change.
- Keep the actively used project-state directory helper unchanged.
- Remove all current tests and documentation that imply the deleted API remains
  supported.

**Non-Goals:**

- Replacing the helpers with another state abstraction.
- Changing the path or behavior of `get_project_state_dir`.
- Migrating or reading files written by the removed API.

## Decisions

1. Delete the module and exports outright. Aliases, deprecation stubs, import
   fallbacks, and legacy-specific errors would preserve the unsafe contract and
   are therefore excluded.
2. Keep ownership at the tool level through `get_project_state_dir(pack)`.
   Active consumers already use this lower-level primitive and define their own
   storage and concurrency behavior.
3. Remove the dedicated helper tests and documentation examples instead of
   translating them to a replacement abstraction. Focused path tests and active
   consumer tests remain the evidence for the retained primitive.
4. Record the retained and removed public surface in a dedicated OpenSpec
   capability so future package changes cannot silently restore generic state
   helpers.

## Risks / Trade-offs

- [Existing external imports fail after upgrade] → This is an intentional v3
  breaking removal, documented in the public contract with no compatibility
  path.
- [Active project-local storage is accidentally removed] → Preserve
  `get_project_state_dir`, search all consumers, and run its focused tests plus
  the complete `otpack` suite.
