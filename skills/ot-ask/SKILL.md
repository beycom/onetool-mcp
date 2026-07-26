---
name: ot-ask
description: Ask which OneTool skill or capability fits your situation. A user-invoked router over the curated OneTool skill catalog.
user-invocable: true
disable-model-invocation: true
---

# Ask OneTool

## Capability boundary

You do not need to remember every OneTool capability. Describe the outcome you want:

| Situation | Route |
|---|---|
| Calling or discovering any pack or recovering a call | `ot-ref` |
| Installing OneTool or resolving a missing extra/config/secret | `ot-setup` |
| Root serving, Direct API, readiness, reload, stats, logs, or results | `ot-runtime` |
| Navigating a large temporary result | `ot-context` |
| Scaffolding a local OneTool extension | `ot-forge` |
| Inspecting images through OneTool vision | `ot-image` |
| Offloading text or data transformation | `ot-llm` |
| Encrypting, auditing, or changing secrets | `ot-secrets` |
| Configuring, using, or recovering a proxied MCP server | `ot-mcp-proxy` |
| Converting office documents to Markdown | `ot-convert` |
| Reading or mutating workbook structure | `ot-excel` |
| OneTool-bounded remote file operations | `ot-file` |
| Searching a portable managed corpus | `ot-knowledge` |
| Durable agent rules, decisions, or discoveries | `ot-mem` |
| Live editable Excalidraw work | `ot-whiteboard` |
| Architecture-model validation or generation | `ot-arch` |
| Database schema inspection or SQL | `ot-db` |
| Source-based rendered diagrams | `ot-diagram` |
| Private project checkpoints and restore | `ot-localhist` |
| Web, documentation, package, or source research | `ot-research` |
| Browser highlights and click guidance | `ot-browser-guidance` |

Choose conversion versus workbook mutation, transient context versus durable memory or portable
knowledge, static diagrams versus a live whiteboard, and search versus fetching a known URL.

## Workflow

1. State the desired outcome, data/source location, whether mutation is allowed, and any
   freshness/privacy/cost constraint.
2. Choose the narrowest single owner from the table.
3. Route missing pack/extra/library/executable/secret/config to `ot-setup`.
4. Route outbound MCP setup, tools, resources, prompts, or recovery to `ot-mcp-proxy`.
5. Route root runtime, transports, Direct API, reload, stats, logs, or stored results to
   `ot-runtime`.
6. Sequence multiple skills only when the output boundary requires it: discover → inspect →
   mutate → verify.

## Safety and side effects

Routing does not authorize installation, config edits, secret changes, connections, filesystem or
database mutation, or external publication. Preserve the user's requested surface when they name
one. Do not route annotation helpers as if they perform browser interaction.

## Verification and recovery

When availability affects the route, inspect the smallest live surface with
`__ot ot.packs(pattern='<pack>', info='min')` or `__ot ot.status()`. A missing runtime pack is
different from a missing capability guide: name which is absent and offer installation or
configuration guidance without changing the environment. If two owners remain plausible, explain
the boundary and choose based on the required output/side effect rather than invoking both.

<!-- BEGIN GENERATED:CATALOG_COVERAGE -->
## Catalog coverage

**Role:** `catalog-router`

| Skill | Role | Purpose |
|---|---|---|
| `ot-ref` | `shared-reference` | Shared OneTool call, discovery, safety, and recovery reference |
| `ot-setup` | `setup` | Diagnose and guide approved OneTool installation and configuration work |
| `ot-runtime` | `runtime-operations` | Operate, observe, and recover the OneTool root runtime |
| `ot-mcp-proxy` | `proxy-lifecycle` | Configure, use, and recover arbitrary outbound MCP proxy servers |
| `ot-context` | `capability-owner` | Store and retrieve large structured tool results |
| `ot-forge` | `capability-owner` | Create and statically validate OneTool extensions |
| `ot-image` | `capability-owner` | Load, inspect, compare, and manage image handles |
| `ot-llm` | `capability-owner` | Transform text or files with a configured language model |
| `ot-secrets` | `capability-owner` | Manage OneTool secret storage safely |
| `ot-convert` | `capability-owner` | Convert office and document formats to useful outputs |
| `ot-excel` | `capability-owner` | Inspect and mutate Excel workbooks with readback |
| `ot-file` | `capability-owner` | Resolve, inspect, search, and mutate files safely |
| `ot-knowledge` | `capability-owner` | Build, maintain, query, and use knowledge bases |
| `ot-mem` | `capability-owner` | Maintain persistent topic-based memory |
| `ot-whiteboard` | `capability-owner` | Create and operate live Excalidraw whiteboards |
| `ot-arch` | `capability-owner` | Validate and generate architecture model artifacts |
| `ot-db` | `capability-owner` | Inspect and query databases with explicit mutation intent |
| `ot-diagram` | `capability-owner` | Select and render diagrams with provider-aware safety |
| `ot-localhist` | `capability-owner` | Maintain project-local snapshot history |
| `ot-research` | `cross-pack-selection` | Select and sequence research, documentation, and package sources |
| `ot-browser-guidance` | `cross-pack-selection` | Use OneTool browser annotation companions with the matching MCP proxy |

For a missing pack, dependency, secret, or config field, inspect `ot.help(query='<pack>', topic='setup')` and hand off to `ot-setup`. For outbound MCP server setup or lifecycle, hand off to `ot-mcp-proxy`.
<!-- END GENERATED:CATALOG_COVERAGE -->
