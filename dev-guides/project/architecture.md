# Architecture

OneTool has one `src/onetool` package. The CLI loads strict config before creating a runtime. `check-config`, help and version do not import the gateway.

`config.py` owns safe YAML, schema validation, interpolation, path normalization and configured-secret collection; `composition.py` adds bounded local includes and winning-file provenance. `secrets.py` owns explicit file/identity operations and lazy decryption. It resolves executable paths without following virtualenv symlinks.

`gateway.py` owns one runtime object and process-local observations. Each server uses canonical FastMCP config conversion and a public StatefulProxyClient with explicit `mode="auto"`. Public `new_stateful()` retains the backend connection for ingress lifetime. A public transport stderr option discards untrusted child stderr. No SDK/FastMCP private state is read or changed.

Native ProxyProvider and namespace transforms supply tools/resources/prompts. A small documented Provider delegates the current backend catalog and rejects collisions before upstream deduplication. Tool dispatch uses the longest configured server-name prefix. A request-local ContextVar memo avoids repeated CodeMode catalog listings within a sequential execute; it is discarded after that request. `cache_ttl=0` keeps discovery fresh across requests.

The inner FastMCP server applies native CodeMode. The outer server registers `onetool_status`, `onetool_reload`, `onetool_servers` and `onetool_results` outside that transform. Root request middleware keeps negotiation and admin lookup from connecting to upstreams.

Runtime-owned ContextVars carry the execution deadline, catalog permission/memo and request log correlation. Each backend uses the smaller remaining/server timeout. One shared public Monty provider adds exact awaited dot calls, per-feed print capture, presentation and bounded batches; native CodeMode still owns tool dispatch. Monty owns compute/memory limits and CodeMode enforces the shared tool-call budget. The gateway owns admission and result handling, not an interpreter.

`operations.py` validates a reload before draining active work for at most five seconds. It records cancellations it initiates so only those become explicit unknown-outcome tool errors. Client/shutdown cancellation propagates. Reload replaces all backends; restart closes one. Session controls drain only the target server; restart refreshes its validated disk definition. Public client clear and transport close handle connection/process cleanup.

`preflight.py` inspects static references before dispatch. Its separate check tool uses cached catalogs and provisional syntax only; P25 proved native Monty type checking rejects valid top-level return. `discovery.py` adds help through public discovery_tools.

`results.py` writes oversized final results to owner-only temp files with hashes and previews. It applies per-result/directory/handle limits and removes the directory on orderly shutdown. Admin/Python retrieval share that file store. Bounded encoding precedes normalization of derived answers. One query/grep worker retains its slot after caller cancellation until the future completes, without delaying cancellation. Upstream reception can allocate much more memory first; see [the measured limit](../../docs/troubleshooting.md#large-responses-and-memory).

`diagnostics.py` owns JSON event sinks, redaction, message cap and rotation. No call site logs code, arguments, results or exception payloads. Status keeps short redacted exception text. OAuth storage uses upstream KeyringStore with a secure-backend check, including secure-only chains. Token acquisition/refresh/identity remain upstream behavior.

There are no packs, dynamic extensions, persistent Python sessions, automatic tool retries, global runtime singleton or duplicate sync API. Monty owns its sandbox subprocess workers; OneTool adds no independent worker pool. The retained V3-line release is an external upstream.

Private planning contains the authoritative bundle, POCs, upstream issue drafts and evidence. Source builds without it. Known upstream gaps have local drafts because external filing is not authorized. Remove local stand-ins when a tested upstream API replaces them.
