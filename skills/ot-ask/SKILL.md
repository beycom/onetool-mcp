---
name: ot-ask
description: Ask which OneTool skill or capability fits your situation. A user-invoked router over the curated OneTool skill catalog.
user-invocable: true
disable-model-invocation: true
---

# Ask OneTool

You do not need to remember every OneTool capability. Describe the outcome you want:

| Situation | Route |
|---|---|
| Calling or discovering any pack or recovering a call | `ot-ref` |
| Navigating a large temporary result | `ot-context` |
| Scaffolding a local OneTool extension | `ot-forge` |
| Inspecting images through OneTool vision | `ot-image` |
| Offloading text or data transformation | `ot-llm` |
| Encrypting, auditing, or changing secrets | `ot-secrets` |
| Managing a proxied MCP server | `ot-servers` |
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
Sequence only when needed: discover → inspect → mutate → verify.

When availability affects the route, inspect the smallest live surface with
`__ot ot.packs(pattern='<pack>', info='min')` or `__ot ot.status()`. A missing runtime pack is
different from a missing capability guide: name which is absent and offer installation or
configuration guidance without changing the environment.
