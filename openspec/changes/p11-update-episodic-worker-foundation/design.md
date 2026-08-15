## Context

The existing implementation already provides serialized `worker.run` execution,
fresh Codex threads, strict whole-state Context, and a three-field public result.
Its artifacts and runtime do not yet agree on channel ownership: completed output
is relayed through `message`, and Console publication, VCS-independent Local
Changes observation, and mechanical History are not enforced as one lifecycle.

The foundation remains one main conversation delegating to one worker. Only Chat
and committed Context may enter a fresh worker automatically. Context and Console
bodies must remain unavailable to the main agent, and no design may introduce
fan-out, recursion, or a second active worker.

## Goals / Non-Goals

**Goals:**

- Establish one enforceable six-channel contract.
- Route substantial user-facing output through the existing Console outbox while
  keeping public Status bounded.
- Record mechanical episode facts and changed paths without creating memory or a
  transcript.
- Make terminal ordering and partial-failure behavior deterministic.
- Preserve fresh-thread isolation, exact authority propagation, atomic Context,
  serialization, and non-replay.

**Non-Goals:**

- Autonomous additional turns, managed artifacts, warm runtime, advanced
  telemetry, or semantic compaction.
- Indexed History, durable Console replay, selective Context queries, partial
  Context updates, retries, transcripts, or long-term memory.
- Compatibility aliases for the original output semantics or change name.

## Decisions

### 1. Treat channels as ownership boundaries

The runtime and agent instructions use this fixed routing table:

| Channel | Writer | Reader | Durable form | Automatic worker input |
|---|---|---|---|---|
| Chat | User and main agent | Current worker | Main conversation | Current request only |
| Context | Worker proposes; MCP commits | Later workers in session | `context.yaml` | Complete snapshot |
| Console | Worker through `console.show` | User | Existing runtime body store/outbox | Never |
| Local Changes | Worker file tools | Workspace and later workers | Project filesystem | Normal file access only |
| Status | Worker and MCP | Main agent and user | `worker.run` result | Never |
| History | MCP only | Explicit inspectors | `history.jsonl` | Never |

Source text, tool results, intermediate reasoning, and same-thread messages are
ephemeral. A reference across channels never copies the referenced body.

Alternative: return all worker output to the main agent. Rejected because it
recreates the conversation growth and Context leakage the architecture removes.

### 2. Publish user-facing bodies through the existing Console

Workers use the existing `console.show` operations for substantial answers,
reports, evidence, previews, and file references. The worker terminal output does
not contain a Console body. The runtime mechanically observes Console message IDs
created during the episode and may retain only their ID and kind in History.

The public result remains exactly `session_id`, `status`, and `message`.
`message` is limited to 1024 UTF-8 bytes after runtime warnings are added. For
`completed`, it is a control receipt; for `needs_input`, it is one direct question;
for failures and interruption, it is a bounded diagnostic. Oversized or
substantial completed terminal text is invalid rather than silently truncated.

Alternative: add worker-specific Console storage. Rejected because the existing
outbox already supplies the user-facing data plane and a second store would blur
ownership.

### 3. Observe Local Changes with project-tree fingerprints

Immediately before worker startup, the MCP walks the project root and records a
bounded fingerprint for regular files. It excludes `.git`, OneTool runtime state,
configured cache roots, and symlink targets outside the project. The final walk
uses the same rules. Comparing the two maps yields sorted project-relative
`created`, `modified`, and `deleted` paths, including further changes to files
that were already dirty before the episode.

The observer does not read file bodies into History, retain snapshots, compute or
store diffs, invoke Git, depend on Localhist, roll back work, or treat symlink
targets outside the project as project files.

Alternative: use `git diff`. Rejected because untracked projects, ignored files,
and pre-existing dirty files make VCS state an incomplete episode boundary.

### 4. Append one strict mechanical History record

Each terminal episode owns an opaque episode ID. After terminal processing,
thread cleanup, and the final file scan, the MCP appends one canonical JSON object
plus LF to `episodic-context/<session-id>/history.jsonl`, flushes, and calls
`fsync`. Serialization gives the journal one writer.

Schema version 1 contains only runtime-observed fields: episode ID, UTC start and
finish timestamps, public terminal status, turn count, Context revisions before
and after, Console message ID/kind pairs, whether Local Changes observation
succeeded, sorted changed path/classification pairs, an optional bounded failure
classification, and bounded warning codes. Unknown fields are rejected by an
explicit reader. Prompts, agent prose, Context bodies, Console bodies, file
contents, diffs, tool results, and narrative summaries are prohibited.

Readers accept complete valid lines in order and ignore only one malformed final
line, preserving earlier records after an interrupted append. They reject a
malformed non-final record.

Alternative: reuse Context or telemetry. Rejected because History is a
mechanical audit, not current semantic state or performance evidence.

### 5. Use one deterministic terminal sequence

After the worker produces a terminal payload, the runtime performs:

1. validate terminal Status and optional complete Context;
2. commit valid Context for `completed` or `needs_input`, otherwise preserve it;
3. delete the worker thread;
4. perform the final Local Changes scan;
5. append History;
6. return bounded Status.

Console publication and Local Changes can occur during the worker turn and are
not reversible. A Context failure changes the terminal outcome to `failed` and
preserves the last valid revision. Cleanup, final-scan, or History failures add a
bounded warning code without reversing a known worker result, Console delivery,
Context commit, or filesystem effect. A History failure cannot record itself.

`needs_input` follows the same sequence and always deletes its thread before the
question returns. The user's answer starts a new `worker.run` episode with the
same session ID and committed Context.

### 6. Preserve exact worker authority and isolation

The main agent supplies absolute current-project `cwd`, `approval_policy: never`,
and a typed read-only, workspace-write, danger-full-access, or external-sandbox
policy. Network mode, writable roots, and temporary-directory exclusions are
preserved exactly. Unsupported envelopes fail before thread startup.

The fresh worker loads the same project instructions, skills, tools, plugins,
and configured MCP servers. The child is marked so `worker.run` rejects recursive
calls, and a process-wide non-blocking lock rejects concurrent calls.

## Risks / Trade-offs

- **Console is process-scoped** → Keep durable replay explicitly deferred; History
  stores only body-free identifiers.
- **Tree scans add episode latency** → Exclude runtime/cache roots, fingerprint
  mechanically, and keep serialized execution so no merge protocol is needed.
- **A crash can leave one partial History line** → Flush and `fsync`; readers
  preserve valid prefix records and ignore only a malformed final line.
- **Bounded Status can be too small for a deliverable** → Require Console for
  substantial output and reserve Status for receipts, questions, and diagnostics.
- **Post-terminal failures cannot undo side effects** → Return explicit warning
  codes and preserve the known outcomes instead of claiming rollback.

## Migration Plan

1. Rename the existing active change without retaining an alias.
2. Update artifacts and tests to the six-channel contract while preserving the
   checked original-v1 task evidence.
3. Implement and verify Console routing, Local Changes observation, History, and
   bounded Status as one lifecycle.
4. Promote only verified behavior to `arch.md`, keep unrelated deferred material
   in `next.md`, and update reference documentation.
5. Run strict OpenSpec validation and project checks, then sync the delta specs
   into the main spec set before dependent implementations are integrated.

Rollback before spec sync is a normal code revert that preserves the last valid
Context and project files. History and Console bodies are observational records;
rollback does not fabricate or delete episode evidence.

## Open Questions

None. The foundation choices are fixed by the delivery plan; extensions remain
separate OpenSpec changes.
