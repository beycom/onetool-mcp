# T3Code as the Episodic Worker Console

## Status

This document is a non-normative implementation proposal. It records how a
T3Code fork could present OneTool Console messages as a separate application
surface. It does not change the episodic-worker, Console outbox, T3Code, or
provider contracts.

Research is based on T3Code commit
[`2f486ab80c748b4d8e3d3b17e49b5a327cb93335`](https://github.com/pingdotgg/t3code/tree/2f486ab80c748b4d8e3d3b17e49b5a327cb93335).
T3Code is changing rapidly, so implementation should revalidate the cited
seams against the selected fork revision.

## Conclusion

T3Code is a better host for a first-class Console surface than either the stock
Codex or Claude Code TUI. T3Code owns the client UI, authenticated client/server
transport, and provider process boundary. It can therefore display Console
messages without terminal scraping, provider display hooks, transcript messages,
or changes to Codex or Claude Code.

The recommended path is:

1. Validate the experience by opening the existing OneTool Console web app in
   T3Code's desktop Preview panel.
2. Add a native, read-only Console right-panel surface backed by a T3Code
   server-side adapter to the existing `onetool-console` HTTP/SSE API.
3. Add remote, mobile, exact-thread correlation, and hardened file delivery.
4. If the sidecar becomes an operational burden, extract the reusable Console
   consumer from `onetool-console` and embed it in the T3Code server.

The native Console stream must remain independent of T3Code orchestration and
provider events. Console bodies must never be inserted into chat, persisted in
the orchestration event store, or sent to a model automatically.

## Architectural constraints

This integration must preserve the channel boundary in `../arch.md`:

| Channel | T3Code treatment |
|---|---|
| Chat | Existing T3Code conversation and provider requests |
| Context | Loaded only through the episodic-worker contract |
| Console | Independent read-only user interface and data stream |
| Local Changes | Existing project files and T3Code file/diff surfaces |
| Status | Bounded `worker.run` result in the normal tool interaction |
| History | Explicit OneTool inspection only; not a Console data source |
| Artifacts | Explicit open/list operations; not automatically copied into Console |

In particular:

- Console is a user-facing data plane, not another assistant message role.
- Provider adapters must not translate Console messages into provider events.
- T3Code orchestration reducers and persisted thread events must not own Console
  bodies.
- Console consumption remains cursor-only and must not acknowledge or mutate
  OneTool producer state.
- A reconnect, reload, or second T3Code client must remain an independent
  consumer.
- File access must retain OneTool Console's allowed-root, path traversal, and
  symlink protections.

## Why T3Code fits

T3Code already has the required structural seams:

- One Node server is the execution and security boundary for web, desktop, and
  mobile clients.
- Clients communicate with it through an authenticated Effect RPC WebSocket.
- The web/desktop application has a thread-scoped right-panel surface model for
  files, diffs, previews, terminals, pull requests, and agents.
- The mobile application has an inspector stack that can own a Console mode.
- Codex is already driven through Codex App Server, while Claude is driven
  through its agent SDK. T3Code is already a custom presentation client rather
  than a wrapper around the providers' terminal renderers.
- Per-thread provider subprocesses accept a controlled environment, providing a
  future seam for opaque host correlation metadata.

Relevant T3Code source locations at the researched commit include:

| Concern | Location |
|---|---|
| Server/client and Effect RPC architecture | `docs/internals/overview.md` |
| RPC contract group | `packages/contracts/src/rpc.ts` |
| Right-panel state | `apps/web/src/rightPanelStore.ts` |
| Right-panel UI | `apps/web/src/components/RightPanelTabs.tsx` |
| Chat/right-panel composition | `apps/web/src/components/ChatView.tsx` |
| Mobile inspector stack | `apps/mobile/src/features/threads/thread-inspector-content-stack.tsx` |
| Codex thread runtime | `apps/server/src/provider/Layers/CodexSessionRuntime.ts` |
| Codex adapter environment | `apps/server/src/provider/Layers/CodexAdapter.ts` |

## Integration options

### Option A: existing Console UI in the Preview panel

Run `onetool-console serve` as a T3Code project script and configure its local
URL as the script's `previewUrl` with `autoOpenPreview` enabled.

This is the preferred UX prototype because it reuses the complete existing
Console server and UI without modifying T3Code source.

Limitations:

- T3Code currently treats embedded preview as a desktop capability.
- A fixed local port can collide with another Console process.
- T3Code does not own sidecar discovery, startup readiness, or shutdown.
- A browser or mobile client cannot safely use its own `127.0.0.1` to reach a
  Console running beside a remote T3Code server.
- The Preview surface does not provide native Console unread state or
  thread/project filtering.

This option validates layout and workflow only. It is not the target remote
architecture.

### Option B: native panel with HTTP/SSE bridge

Add a T3Code server service that consumes an existing `onetool-console serve`
process:

- subscribe to `GET /api/events` for revision notifications;
- refresh `GET /api/instances` and filtered `GET /api/messages` reads;
- fetch a selected message from `GET /api/messages/:instance/:id`;
- proxy `GET /api/files/preview` and `GET /api/files/blob` through T3Code's
  authenticated server boundary; and
- translate those reads into typed T3Code RPC snapshots and deltas.

This is the recommended first native implementation. It minimizes cross-repo
work and uses the already tested Console protocol, signed outbox consumer,
multi-instance discovery, bounded read model, retention-gap diagnostics, and
file authorization.

Its main cost is an extra local process plus configuration or discovery of its
base URL.

### Option C: embedded Console consumer

Extract a reusable package from `onetool-console` containing:

- Direct API instance discovery;
- signed outbox request and response verification;
- protocol validation;
- independent cursors and retention-gap detection;
- the bounded instance/message read model; and
- revision subscriptions.

Use that package in both the existing Console server and the T3Code server. The
T3Code process would then read the OneTool outbox directly and no Console
sidecar would be required.

This is the cleanest end state for installation, lifecycle, remote access, and
observability, but it should follow the native bridge unless sidecar operation
is already known to be unacceptable. It creates a shared-package compatibility
and release relationship between two repositories.

### Rejected approaches

| Approach | Reason |
|---|---|
| Inject Console bodies through Codex or Claude hooks | Provider-specific and risks adding Console content to the conversation or model context |
| Convert Console messages into orchestration messages | Pollutes the transcript, duplicates potentially large bodies, and weakens channel isolation |
| Add Console handling to each provider adapter | Console is provider-neutral and would be inconsistently available across providers |
| Read the OneTool outbox directly from web/mobile clients | Exposes auth material and local paths, and fails when the T3Code server is remote |
| Iframe a client-local Console URL as the final design | Incorrect host boundary for remote clients and weak lifecycle/auth integration |
| Correlate through PIDs or process-tree inspection | Brittle across restarts, remote providers, shells, and operating systems |
| Infer Console output by parsing `worker.run` messages | Status is deliberately bounded and does not contain the substantial Console body |

## Target data flow

```text
OneTool MCP Direct API
  signed bounded outbox
          |
          v
onetool-console consumer/read model
  Option B: Console sidecar HTTP + SSE
  Option C: library embedded in T3Code server
          |
          v
T3Code Console service
  project/thread filter
  metadata subscription
  lazy message and file reads
          |
          v
authenticated Effect RPC
          |
          +--> web/desktop Console right-panel surface
          +--> mobile Console inspector

There is deliberately no path from this stream to provider adapters,
orchestration messages, Context, History, or model requests.
```

The T3Code server is the only client-facing authority. It resolves project and
thread scope, withholds outbox keys, validates Console responses, enforces file
authorization, and provides one transport that works for local and remote
clients.

## T3Code contract and service shape

Exact Effect schemas and RPC names should follow the conventions at the chosen
T3Code revision. Conceptually, the addition needs:

### Shared contracts

Add `packages/contracts/src/console.ts` with types for:

- `ConsoleInstanceSummary`;
- `ConsoleMessageSummary` containing metadata and bounded preview only;
- `ConsoleMessageDetail` for a selected body or reference;
- `ConsoleRevision` or delta notification;
- retention-gap and connection-health state; and
- project/thread scope identifiers.

Add typed RPC operations equivalent to:

```text
console.subscribe(scope) -> stream<snapshot-or-delta>
console.getMessage(scope, instanceId, messageId) -> detail
console.getFile(scope, instanceId, messageId, representation) -> authorized body
console.getDiagnostics(scope) -> bounded diagnostics
```

Names are illustrative. The implementation should prefer a snapshot followed
by revision/delta events if that matches T3Code's existing subscription style.

### Server service

Add a feature-owned service under `apps/server/src/console/` that:

- owns the Console connection and reconnection lifecycle;
- maps T3Code projects and threads to Console instances;
- coalesces bursts of SSE revision events before refreshing metadata;
- keeps only bounded summaries needed by subscribed clients;
- fetches full inline bodies only when selected;
- proxies file and image content without disclosing server-local paths or keys;
- reports disconnected, stale, invalid-signature, and retention-gap states; and
- stops watchers when no project needs them.

Do not add Console events to T3Code's orchestration event store. Durable Console
retention remains a Console capability, not a T3Code thread capability.

### Client runtime

Add feature-owned state under `packages/client-runtime/src/state/console.ts`.
Following T3Code's right-panel pattern, durable resource state belongs to the
feature rather than `rightPanelStore` itself.

Client state may own:

- current instance/message selection;
- filters by kind and instance;
- unread and last-seen revision state;
- loading and reconnect presentation; and
- a bounded detail cache.

Unread state is a presentation concern. Marking a tab read must not acknowledge
or mutate OneTool's producer outbox.

## User interface

Add a singleton `console` kind to the right-panel surface union and render a
native `ConsolePanel` in `ChatView`/`RightPanelTabs`.

The initial panel should provide:

- a visible Console tab with unread count or activity indicator;
- instance and message-kind filtering;
- newest-first or stable chronological message navigation;
- a master/detail layout that remains usable in a narrow panel;
- clear connected, disconnected, stale, and retention-gap states;
- lazy rendering of the selected message; and
- explicit open-in-file/diff actions where a message refers to project files.

Reuse T3Code renderers where their trust and data contracts fit, including its
Markdown, code, file, and diff components. Add dedicated renderers for Console
kinds such as JSON, YAML, tables, Mermaid, images, and generic files where
necessary. Treat Markdown, SVG, HTML-like content, terminal control sequences,
and Mermaid source as untrusted input.

Mobile should use a dedicated Console inspector mode or route with the same RPC
contract. It should not attempt to load a URL hosted on the mobile device's
loopback interface.

## Project and thread correlation

### Project-scoped MVP

Console instance snapshots already include `cwd`, `repo_root`, `allowed_roots`,
and arbitrary `runtime` metadata. The first implementation should match
canonical T3Code project workspace roots against canonical Console `repo_root`
or `cwd` values.

Project scope is deterministic and useful, but multiple T3Code threads in the
same worktree will see the same Console stream.

### Exact thread correlation

When exact filtering is justified, T3Code should inject opaque metadata into
the provider/MCP child environment, for example:

```text
ONETOOL_HOST=t3code
ONETOOL_HOST_PROJECT_ID=<opaque T3Code project ID>
ONETOOL_HOST_THREAD_ID=<opaque T3Code thread ID>
```

OneTool can copy these values into the existing arbitrary
`instance.snapshot.runtime` object. T3Code then prefers exact host-thread
matching and falls back to project-root matching when the metadata is absent.

Properties of this design:

- it does not expose or depend on provider thread IDs;
- it works for both Codex and Claude when OneTool MCP inherits their controlled
  environment;
- it requires no new Console protocol field; and
- it degrades to project scope for shared remote MCP servers that cannot inherit
  the per-thread environment.

Adding host metadata to OneTool runtime behavior is a separate user-facing
contract change and requires OpenSpec before implementation in this repository.

Episode ID and Context name could also be published as Console message metadata
by the active worker runtime. They would improve grouping within a thread but do
not replace host project/thread correlation.

## Security and remote behavior

- Never send the Console outbox HMAC key to any T3Code client.
- Do not expose arbitrary server-local filesystem reads through a generic path
  query.
- Bind every detail or file request to the subscribed project/thread scope and
  verify that the instance belongs to that scope.
- Preserve the producing instance's allowed roots and reject traversal,
  absolute-path substitution, and symlink escapes.
- Authenticate Console RPCs with T3Code's existing client/server session. A
  dedicated `console:read` permission can be considered if T3Code's authorization
  model needs finer separation; otherwise the existing project/thread read scope
  should gate the initial feature.
- Sanitize all active content and avoid executing HTML, scripts, remote URLs, or
  terminal escape sequences from messages.
- Bound message summaries, detail responses, file previews, render time, and
  client caches independently.
- A remote browser or mobile app always reaches Console through the remote
  T3Code server, never through client loopback.

## Performance and lifecycle

Console can retain many messages and some bodies can be large. The integration
should therefore:

- stream revisions, message metadata, and bounded previews rather than all
  bodies;
- request one selected body or file representation lazily;
- paginate historical summaries;
- coalesce rapid revision notifications;
- share one server-side Console connection/read model across eligible clients;
- use stable IDs to avoid rerendering unchanged messages;
- discard or cap client detail caches; and
- surface retention gaps explicitly instead of pretending the local history is
  complete.

For Option B, T3Code must define who starts the sidecar, how readiness is
detected, how a port is selected, whether an existing compatible process may be
reused, and when a T3Code-owned process is stopped. The prototype may leave
these operations manual; the native phase may not.

## Delivery phases

### Phase 0: desktop UX validation

- Configure a T3Code project script that runs `onetool-console serve`.
- Open its URL in the desktop Preview panel.
- Exercise worker output involving text, Markdown, code, diffs, files, and
  images.
- Validate whether a right-panel workflow is preferable to a separate terminal
  split or popup.
- Record panel width, unread indication, filtering, and navigation requirements.

Exit gate: users can follow an episodic worker from Chat to substantial Console
output without confusing Console with chat or Status.

### Phase 1: native web/desktop panel

- Add Console schemas and typed RPC operations.
- Add the server-side HTTP/SSE bridge to the existing Console server.
- Add client-runtime subscription, selection, unread, and bounded cache state.
- Add the web/desktop Console right-panel surface.
- Stream summaries and lazily fetch selected bodies.
- Keep project-root scoping; do not require exact thread correlation yet.

Exit gate: Console is native, read-only, independently streamed, and absent from
all orchestration transcripts and provider requests.

### Phase 2: production boundary

- Add authenticated file/image proxying with full allowed-root tests.
- Add robust reconnect, sidecar lifecycle, diagnostics, and retention-gap UI.
- Add the mobile Console inspector.
- Add exact T3Code host project/thread metadata if project-only scope proves
  insufficient.
- Test local desktop, remote web, and mobile-to-remote-server topologies.

Exit gate: all supported T3Code surfaces use the server boundary correctly and
cannot obtain Console data outside their authorized project/thread scope.

### Phase 3: optional embedded consumer

- Extract the reusable signed outbox consumer and bounded read model from
  `onetool-console`.
- Adopt it in the existing Console server without changing its public API.
- Adopt it in the T3Code server and remove the sidecar dependency.
- Define cross-repository versioning, release, and compatibility ownership.

Exit gate: T3Code provides the same independent-consumer and security semantics
without requiring a separate Console process.

## Verification matrix

At minimum, implementation should verify:

| Area | Required evidence |
|---|---|
| Channel isolation | Console bodies never appear in T3Code orchestration events, persisted chat, worker Context, or provider requests |
| Independent consumption | Multiple clients maintain their own views without acknowledging producer state |
| Scoping | Correct behavior for separate projects, worktrees, multiple threads in one worktree, and missing host metadata |
| Reconnect | SSE/RPC reconnect resumes cleanly and exposes retention gaps |
| Bounds | Summaries are paged, bodies are lazy, and WebSocket transfer/cache limits are enforced |
| File security | Traversal, absolute substitution, unauthorized roots, and symlink escapes fail closed |
| Rendering | Markdown, Mermaid, images, diffs, and control sequences are handled as untrusted content |
| Topology | Desktop-local, browser-remote, and mobile-remote behavior use the correct server host |
| Lifecycle | Sidecar start, readiness, collision, reuse, failure, and shutdown behavior are deterministic |

## Change ownership

The work spans two repositories and should remain separated by contract:

- A native T3Code panel and bridge are T3Code changes.
- An extracted reusable Console consumer is an `onetool-console` change.
- Host/thread runtime metadata or episode metadata is a OneTool behavior change
  and requires a dedicated OpenSpec change before implementation.
- The existing episodic-worker channel model does not need to change.

T3Code currently states that large upstream features are generally not being
accepted. Initial work should therefore target a personal fork. If proposed
upstream later, describe the feature generically as a read-only external output
channel with typed adapters, rather than coupling T3Code directly to OneTool.

## Open decisions

Before Phase 1 implementation, decide:

1. Whether T3Code owns the Console sidecar lifecycle or connects to a separately
   managed process.
2. How the server discovers the Console base URL without hard-coded origins.
3. Whether project-wide visibility is sufficient for the first sustained use.
4. Whether unread state is per device, per authenticated user, or ephemeral per
   client session.
5. Which Console kinds must render natively in the first release.
6. Whether T3Code's current authorization scopes are sufficient or need an
   explicit read-only Console scope.
7. What measurements would justify extracting and embedding the Console
   consumer instead of retaining the HTTP/SSE boundary.

None of these decisions permits Console content to become implicit model input.
