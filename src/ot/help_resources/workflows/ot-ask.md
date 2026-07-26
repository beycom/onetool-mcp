<!-- Generated from skills/ot-ask/SKILL.md; do not edit. -->
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
