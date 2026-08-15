## Why

The episodic worker is implemented, but its original contract lets substantial
worker output pass through Status and does not normatively define the Console,
Local Changes, or mechanical History boundaries. The foundation must be made
internally coherent before independent extensions build on it.

## What Changes

- Define the six channels—Chat, Context, Console, Local Changes, Status, and
  History—with explicit writers, readers, persistence, and automatic-input rules.
- **BREAKING**: Make worker `message` a bounded control Status rather than a
  carrier for substantial completed output; workers publish substantial output
  through the existing Console channel.
- Keep committed Context private to successive workers in the same session and
  accept only a validated complete replacement on a successful terminal outcome.
- Add a strict, versioned, MCP-authored `history.jsonl` record after each episode,
  without prompts, narrative summaries, file contents, diffs, Console bodies, or
  tool results.
- Observe created, modified, and deleted project paths mechanically with a
  VCS-independent pre/post scan; Local Changes remain ordinary project files.
- Require `needs_input` to terminate and delete the current worker thread; the
  answer starts a fresh episode with the same session and committed Context.
- Preserve one active worker, no recursion or fan-out, no automatic retry, and
  the main agent's exact effective instructions, capabilities, and permissions.
- Specify failure ordering and bounded warnings for Context handling, Console
  publication, thread cleanup, change observation, and History append.

## Capabilities

### New Capabilities

- `episodic-context`: Private whole-state Context plus the session-owned,
  mechanical History journal and their isolation rules.
- `tool-worker`: Serialized fresh-thread worker execution, channel routing,
  Local Changes observation, bounded Status, cleanup, and failure semantics.
- `skill-episodic-orchestrator`: Explicit coordination that delegates work while
  keeping Context and Console bodies out of the main conversation.

### Modified Capabilities

- `serve-configuration`: Add strict worker routing and Context-size settings.
- `serve-skills`: Distribute the explicit episodic-orchestrator skill.

## Impact

- Affects the worker tool pack, app-server adapter, Context persistence, Console
  integration, project-tree observation, History storage, configuration, skill,
  tests, and worker reference documentation.
- Changes the meaning and permitted size of `worker.run.message` while preserving
  the public three-field result and four public terminal statuses.
- Establishes the normative baseline that `p21` through `p31` depend on; its
  delta specs must be synced before dependent implementation is integrated.
