# TypeScript React UI

Authoritative practice guide for OneTool-owned frontend packages such as `packages/onetool-display-ui`.

## Package Boundaries

- Keep frontend dependencies, scripts, config, tests, and lockfiles inside the owning package.
- Use `npm` with committed `package-lock.json` files. Install with `npm ci`.
- Do not add frontend dependency or tool config to `pyproject.toml`.
- Keep package versions private and decoupled from the Python package unless a future release decision changes that.
- Use Node 22 or newer for Display UI development.

## Commands

Display UI commands live in `packages/onetool-display-ui/justfile` and are called from the repo root as `just display-ui::<task>`.

Core tasks:

- `just display-ui::install`
- `just display-ui::typecheck`
- `just display-ui::lint`
- `just display-ui::test-unit`
- `just display-ui::test-e2e`
- `just display-ui::deps-check`
- `just display-ui::build`
- `just display-ui::check`

Root commands may orchestrate frontend work, but should not grow one root recipe per frontend action.

## TypeScript And React

- Keep TypeScript strict and fix type errors at the source.
- Prefer small typed components with explicit props.
- Keep server state in TanStack Query. Use query keys shaped by domain and instance, for example `["display", instanceId, "messages"]` and `["display", instanceId, "payload", messageId]`.
- Keep view-only UI state in React state: selected message, panel width, rich/raw toggles, theme, scroll state, and transient popover state.
- Use targeted memoization for virtualization, stable callbacks passed to memoized children, expensive derivations, and effect dependencies.
- Do not add React Compiler in this phase. Avoid broad defensive `memo`, `useMemo`, or `useCallback` churn without a measured reason.

## Styling

- Tailwind v4 is the default utility engine for frontend packages that opt in.
- Use semantic classes and CSS variables for dense operational surfaces, shared layout, theme tokens, and component states.
- Use Tailwind utilities where they make local spacing, typography, or layout clearer.
- Extract a component when a repeated class pattern carries behavior or state, not just to hide one line of styling.
- Keep design tokens in CSS variables when they need to be reused across semantic classes or themes.

## Accessibility

- Use native controls first.
- Segmented controls should expose selected state and keyboard movement.
- Resizers should use separator semantics, `aria-valuemin`, `aria-valuemax`, `aria-valuenow`, and keyboard support.
- Icon-only buttons need `aria-label` and a visible hover title or tooltip.
- Keep focus behavior predictable when virtualized rows mount and unmount.

## Renderer Safety

Display renderers handle local artifacts that may still be untrusted.

- Do not insert unsanitized HTML or SVG with `innerHTML`.
- Sanitize Mermaid or generated SVG before DOM insertion.
- Bound structured JSON/YAML parsing and rendering by source size, depth, and sibling count.
- Fall back to raw/source display for oversized, invalid, or unsupported payloads.
- Keep payload previews lazy and bounded. Do not fetch every timeline payload at row render time.
- Add explicit tests for malicious SVG/HTML payloads, oversized structured data, invalid content, and renderer error fallback.

## Testing

Frontend tests stay under the frontend package and run through package scripts, not Python pytest.

- Use Vitest and Testing Library for unit/component behavior.
- Use Playwright for browser flows and axe checks where layout or accessibility needs a real browser.
- Keep Python pytest markers in Python tests only.
- Use realistic local fixtures or stable real sites when browser annotation tests need a page; never use `example.com`.

## Browser Asset Pipeline

Generated JavaScript and HTML assets must be reproducible.

- `packages/onetool-display-ui` owns the Display UI build and packaged HTML asset.
- `src/ot/assets` owns `inject-src.js`, `inject.js`, and annotation asset tests.
- `just display-ui::build` regenerates the packaged Display UI HTML.
- `just build-inject` regenerates `src/ot/assets/inject.js`.
- Release checks must fail when generated assets are stale.
- Generated package-local build output stays ignored unless it is an intentional package asset marker or release artifact.
