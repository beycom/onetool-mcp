# TypeScript React UI

Browser-facing OneTool Console App work lives in the separate sibling project:

```bash
cd /Users/gavin/01-work-thor/projects/group-hobby/onetool-console
npm install
npm run check
```

`onetool-mcp` does not package or build a frontend. It only produces signed Console outbox events and vendored protocol fixtures for compatibility tests.

## Practice

- Keep TypeScript config, npm lockfiles, and frontend tests inside the owning TypeScript package.
- Prefer feature/domain-first source folders, reusable shared primitives, strict TypeScript, Vitest for unit/component behavior, and Playwright for browser flows.
- Treat rendered markdown, code, diffs, images, JSON, YAML, Mermaid, tables, inline payloads, file references, and file diff references as untrusted local content.
- Sanitize generated SVG/HTML, bound JSON/YAML parsing and rendering, and keep source/raw fallbacks for oversized or failed rich rendering.
