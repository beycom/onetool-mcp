## Why

The episodic worker is implemented around one opaque session per main Chat. That
couples unrelated work to one Context, makes fresh review awkward, and exposes
execution-policy plumbing in every call. The foundation is still active and
unsynced, so it should establish named project-local Contexts before independent
extensions build on the obsolete session contract.

The channel contract also remains incomplete: substantial worker output still
passes through Status, while Console, Local Changes, and mechanical History are
not enforced as one lifecycle.

## What Changes

- **BREAKING**: Replace opaque `session_id` continuation with named project-local
  Contexts selected independently for each worker episode.
- Start every orchestrated Chat with selected Context `default`; allow
  `worker.select` to change the Chat selection and an explicit `worker.run`
  Context to override it for one episode.
- Create missing Contexts automatically and store each as one editable bounded
  Markdown file with validated frontmatter containing description, tags, status,
  schema version, and revision.
- Expand the worker pack to `run`, `select`, `list_contexts`, `update_context`,
  and `archive_context`; remove public session and execution-policy parameters.
- Keep Context bodies private to workers while exposing bounded frontmatter
  metadata for discovery and maintenance.
- **BREAKING**: Make worker `message` a bounded control Status rather than a
  carrier for substantial completed output; workers publish substantial output
  through the existing Console channel.
- Store strict MCP-authored project History independently from Context files and
  record only bounded mechanical facts, including the selected Context name.
- Observe created, modified, and deleted project paths mechanically with a
  VCS-independent pre/post scan.
- Preserve fresh worker threads, one active worker, no recursion or fan-out, no
  automatic retry, and the main agent's effective project instructions,
  capabilities, and authority.

## Capabilities

### New Capabilities

- `worker-contexts`: Named project-local Context files, metadata discovery,
  automatic creation, atomic replacement, and archival.
- `tool-worker`: Serialized fresh-thread execution, Context operations, channel
  routing, Local Changes observation, bounded Status, cleanup, and failures.
- `skill-use-worker`: Explicit coordination with one Chat-selected
  Context name and Console/Context isolation.

### Modified Capabilities

- `serve-configuration`: Add strict worker routing and Context-size settings.
- `serve-skills`: Distribute the explicit `use-worker` skill.

## Impact

- Affects the worker tool pack, app-server adapter, Context persistence, Console
  integration, project-tree observation, History storage, configuration, skill,
  tests, and worker reference documentation.
- Removes `session_id` and public `execution`, replaces the public worker result's
  session identity with its effective Context name, and adds four Context
  operations without compatibility aliases.
- Establishes the normative baseline that `p21` through `p31` depend on; its
  delta specs must be synced before dependent implementation is integrated.
