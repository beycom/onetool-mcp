import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";

const root = resolve(new URL("..", import.meta.url).pathname);
const tsc = spawnSync("npx", ["tsc", "--noEmit"], {
  cwd: root,
  stdio: "inherit",
});
if (tsc.status !== 0) {
  process.exit(tsc.status ?? 1);
}

const builtHtml = await readFile(resolve(root, "dist/index.html"), "utf8");
const sourceChecks = [
  ["@vitejs/plugin-react", "vite.config.ts"],
  ['return "rendererMermaid"', "vite.config.ts"],
  ['"dev": "vite"', "package.json"],
  ['"typecheck": "tsc --noEmit"', "package.json"],
  ['"test:unit": "vitest run"', "package.json"],
  ['"lint": "eslint . --max-warnings=0"', "package.json"],
  ["@tanstack/react-router", "src/app/router.tsx"],
  ["@tanstack/react-query", "src/app/App.tsx"],
  ["@tanstack/react-table", "src/features/display/components/PayloadRenderer.tsx"],
  ["/api/admin/instances/", "src/features/display/api.ts"],
  ["@legendapp/list", "src/features/display/components/DisplayTimeline.tsx"],
  ["@base-ui/react/popover", "src/shared/components/ui/Popover.tsx"],
  ['style={{ height: "100%", minHeight: 0, overflowY: "auto" }}', "src/features/display/components/DisplayTimeline.tsx"],
  ["scroll-bottom-button", "src/features/display/components/DisplayTimeline.tsx"],
  ['aria-label="Display message inspector"', "src/features/display/DisplayApp.tsx"],
  ["Open a message in the side panel.", "src/features/display/DisplayApp.tsx"],
  ["store.loadPayload(selectedPanelMessage.id);", "src/features/display/DisplayApp.tsx"],
  ["<MessageRow", "src/features/display/DisplayApp.tsx"],
  ["onToggleRich={togglePanelRich}", "src/features/display/DisplayApp.tsx"],
  ['actionLayout="inspector"', "src/features/display/DisplayApp.tsx"],
  ['aria-label="Resize message inspector"', "src/features/display/DisplayApp.tsx"],
  ['aria-label="Open message in side panel"', "src/features/display/components/MessageRow.tsx"],
  ['aria-label="Show message info"', "src/features/display/components/MessageRow.tsx"],
  ["RenderErrorBoundary", "src/features/display/components/MessageRow.tsx"],
  ['className="message-toolbar"', "src/features/display/components/MessageRow.tsx"],
  ['className="message-action-menu"', "src/features/display/components/MessageRow.tsx"],
  ["Disable rich view", "src/features/display/components/MessageRow.tsx"],
  ["message-action-trigger", "src/features/display/components/MessageRow.tsx"],
  ['layout: "timeline" | "inspector"', "src/features/display/components/MessageRow.tsx"],
  ['actionLayout = "timeline"', "src/features/display/components/MessageRow.tsx"],
  ['className="file-message-header"', "src/features/display/components/MessageRow.tsx"],
  ['className="message-meta"', "src/features/display/components/MessageRow.tsx"],
  ["metadata.", "src/features/display/components/MessageRow.tsx"],
  ["compactMessageId", "src/features/display/components/MessageRow.tsx"],
  ['<CopyMessageButton api={api} message={message} payload={payload} kind="content" />', "src/features/display/components/MessageRow.tsx"],
  ["api.payload(message.id)", "src/features/display/components/MessageRow.tsx"],
  ['kind === "path" ? <FolderTreeIcon', "src/features/display/components/MessageRow.tsx"],
  ['status === "failed"', "src/features/display/components/MessageRow.tsx"],
  ['className={`icon-button row-action row-open', "src/features/display/components/MessageRow.tsx"],
  ["computeStableDisplayRows", "src/features/display/lib/displayRows.ts"],
  ["MAX_PAYLOAD_CACHE_ENTRIES", "src/features/display/lib/displayStore.ts"],
  ["prunePayloadQueries", "src/features/display/lib/displayStore.ts"],
  ["INITIAL_PAYLOAD_PREFETCH_COUNT", "src/features/display/components/DisplayTimeline.tsx"],
  ['className="preview-wrap"', "src/features/display/components/MessageRow.tsx"],
  ["react-markdown", "src/features/display/components/MarkdownRenderer.tsx"],
  ['className="markdown-viewer"', "src/features/display/components/MarkdownRenderer.tsx"],
  ["useDisplaySettings", "src/features/display/components/MarkdownRenderer.tsx"],
  ["copyCode = true", "src/features/display/components/MarkdownRenderer.tsx"],
  ["@pierre/diffs", "src/features/display/lib/diffRendering.ts"],
  ["@pierre/diffs/react", "src/features/display/components/CodeView.tsx"],
  ['import("mermaid")', "src/features/display/components/MermaidViewer.tsx"],
  ["sanitizeMermaidSvg", "src/features/display/components/MermaidViewer.tsx"],
  ['from "yaml"', "src/features/display/components/StructuredDataViewer.tsx"],
  ["STRUCTURED_SOURCE_LIMIT_BYTES", "src/features/display/components/StructuredDataViewer.tsx"],
  ["LazyStructuredDataViewer", "src/features/display/components/PayloadRenderer.tsx"],
  ["showHeader={false}", "src/features/display/components/PayloadRenderer.tsx"],
  ['className="plain-text-payload"', "src/features/display/components/PayloadRenderer.tsx"],
  ["api.preview(path)", "src/features/display/components/PayloadRenderer.tsx"],
  ["MermaidViewer", "src/features/display/components/PayloadRenderer.tsx"],
  ["resolveFileViewerKind", "src/features/display/components/PayloadRenderer.tsx"],
  ["MAX_GRID_ROWS", "src/features/display/components/PayloadRenderer.tsx"],
  ["MAX_GRID_COLUMNS", "src/features/display/components/PayloadRenderer.tsx"],
  ['role="grid"', "src/features/display/components/PayloadRenderer.tsx"],
  ["resolveDiffThemeName(codeTheme)", "src/features/display/components/DiffRenderer.tsx"],
  ['overflow: wrapText ? "wrap" : "scroll"', "src/features/display/components/DiffRenderer.tsx"],
  ['aria-label="Line Wrapping"', "src/features/display/DisplayApp.tsx"],
  [".text-wrap .plain-text-payload", "src/styles/app.css"],
  ["#onetool-admin-root", "src/styles/app.css"],
  [".message-toolbar", "src/styles/app.css"],
  [".message-action-trigger.open", "src/styles/app.css"],
  [".scroll-bottom-button", "src/styles/app.css"],
  [".renderer-error", "src/styles/app.css"],
  [".structured-viewer", "src/styles/app.css"],
  [".structured-body", "src/styles/app.css"],
  [".tree-viewer", "src/styles/app.css"],
  [".markdown-viewer", "src/styles/app.css"],
  [".segmented-control", "src/styles/app.css"],
  [".message-meta", "src/styles/app.css"],
  [".file-message-header", "src/styles/app.css"],
  [".plain-text-payload", "src/styles/app.css"],
  ["--side-panel-width", "src/styles/app.css"],
  [".inspector-payload .code-view", "src/styles/app.css"],
];

for (const [needle, file] of sourceChecks) {
  const content = await readFile(resolve(root, file), "utf8");
  if (!content.includes(needle)) {
    throw new Error(`${file} is missing expected t3code-derived marker ${needle}`);
  }
}

const styles = await readFile(resolve(root, "src/styles/app.css"), "utf8");
if (/\.inspector-payload\s*>\s*\*\s*\{\s*min-height:\s*100%/m.test(styles)) {
  throw new Error("Inspector payload must not force every child to min-height: 100%.");
}
if (!/\.inspector-payload\s*\{[^}]*width:\s*100%;[^}]*height:\s*100%;[^}]*overflow:\s*hidden;/m.test(styles)) {
  throw new Error("Inspector payload must keep message chrome fixed outside the scroll container.");
}
if (!/\.inspector-payload\s+\.message-row-expanded\s*\{[^}]*min-width:\s*100%;[^}]*width:\s*100%;[^}]*height:\s*100%;[^}]*overflow:\s*hidden;/m.test(styles)) {
  throw new Error("Inspector expanded message must fill the panel without becoming the scroll container.");
}
if (!/\.inspector-payload\s+\.message-row-expanded\s+\.preview-wrap\s*\{[^}]*overflow:\s*auto;[^}]*overscroll-behavior:\s*contain;/m.test(styles)) {
  throw new Error("Inspector expanded message preview must own payload scrolling.");
}
if (/\.inspector-payload\s+\.(?:raw-block|code-view|diff-file|data-grid-scroller)[^{]*\{[^}]*overflow-x:\s*auto;/m.test(styles)) {
  throw new Error("Inspector child renderers must not own horizontal scrollbars.");
}
if (!/\.segmented-control\s*\{[^}]*justify-self:\s*start;/m.test(styles)) {
  throw new Error("Segmented controls must not stretch across structured viewer grids.");
}
if (/\.popover-viewport\b/.test(styles)) {
  throw new Error("Popover scrolling must stay on the popup; do not reintroduce a viewport wrapper.");
}
if (!/\.popover-popup\s*\{[^}]*max-height:\s*min\(520px,\s*calc\(100vh - 80px\)\);[^}]*overflow-x:\s*hidden;[^}]*overflow-y:\s*auto;/m.test(styles)) {
  throw new Error("Popover popup must bound static info content and scroll vertically only.");
}
if (/\.popover-popup\s*\{[^}]*overflow:\s*auto;/m.test(styles)) {
  throw new Error("Popover popup must not use two-axis overflow auto.");
}

const popover = await readFile(resolve(root, "src/shared/components/ui/Popover.tsx"), "utf8");
if (popover.includes("PopoverPrimitive.Viewport")) {
  throw new Error("Popover popup must not wrap static content in PopoverPrimitive.Viewport.");
}

const messageRow = await readFile(resolve(root, "src/features/display/components/MessageRow.tsx"), "utf8");
if (!/function compactMessageId\(id: string\): string \{\s*return id;\s*\}/m.test(messageRow)) {
  throw new Error("Message row visible IDs must show the full short display ID.");
}
if (!messageRow.includes('return `${hour}:${minute}, ${day}-${months[date.getMonth()]}`;')) {
  throw new Error("Message timestamps must render as HH:mm, dd-Mon.");
}
if (!messageRow.includes('["Lines", message.preview_lines')) {
  throw new Error("Message info must label preview line count as Lines.");
}
for (const marker of ['["Status", message.status]', '["Payload mode", message.payload.mode]', '"Preview lines"', "metadata.summary"]) {
  if (messageRow.includes(marker)) {
    throw new Error(`Message info must not include ${marker}.`);
  }
}

const copyIndex = messageRow.indexOf('<CopyMessageButton api={api} message={message} payload={payload} kind="content" />');
const infoIndex = messageRow.indexOf("{infoButton}", copyIndex);
const panelIndex = messageRow.indexOf("{panelButton}", infoIndex);
const openIndex = messageRow.indexOf("{openButton}", panelIndex);
if (copyIndex < 0 || infoIndex < 0 || panelIndex < 0 || openIndex < 0 || copyIndex > infoIndex || infoIndex > panelIndex || panelIndex > openIndex) {
  throw new Error("Timeline actions must render as copy content, info, side panel, then open.");
}
if (messageRow.includes("inspectButton") || messageRow.includes("openButton ??")) {
  throw new Error("Timeline rows must not render an open fallback for non-file messages.");
}
const timelineReturnStart = messageRow.indexOf('<CopyMessageButton api={api} message={message} payload={payload} kind="content" />');
const timelineReturnEnd = messageRow.indexOf("</>", timelineReturnStart);
const timelineReturn = messageRow.slice(timelineReturnStart, timelineReturnEnd);
if (timelineReturn.includes("<MessageActionMenu")) {
  throw new Error("Timeline message rows must not render the overflow action menu.");
}
if (!messageRow.includes('<Popover open={open} onOpenChange={setOpen}>')) {
  throw new Error("Message action menu must expose controlled open state for trigger visibility.");
}
if (!messageRow.includes("const runMenuAction = useCallback((action: () => void) => {")) {
  throw new Error("Message action menu must wrap item handlers to close after selection.");
}
if (!messageRow.includes("setOpen(false);")) {
  throw new Error("Message action menu item selection must close the popover.");
}
for (const marker of ["runMenuAction(copyPath.copy)", "runMenuAction(copyContent.copy)", "runMenuAction(onToggleRich)"]) {
  if (!messageRow.includes(marker)) {
    throw new Error(`Message action menu item is missing close wrapper ${marker}.`);
  }
}

if (/\.message-row\.selected\s+\.message-actions/.test(styles)) {
  throw new Error("Selected rows must not force message actions to stay visible.");
}
if (!/\.message-action-trigger\.open\s*\{[^}]*opacity:\s*0;[^}]*pointer-events:\s*none;/m.test(styles)) {
  throw new Error("Open overflow action triggers must hide while their menu is selected.");
}

const payloadRenderer = await readFile(resolve(root, "src/features/display/components/PayloadRenderer.tsx"), "utf8");
if (payloadRenderer.includes("Showing {records.length} of {allRecords.length} rows")) {
  throw new Error("Table previews must not render row/column truncation status text.");
}
if (!payloadRenderer.includes("showHeader={false}")) {
  throw new Error("File-backed source renderers must suppress duplicate inner file headers.");
}
if (payloadRenderer.includes('import { MermaidViewer }') || payloadRenderer.includes('import { StructuredDataViewer }')) {
  throw new Error("Heavy renderers must stay behind lazy component imports.");
}
if (!payloadRenderer.includes("lazy(() => import(\"./MermaidViewer\")")) {
  throw new Error("Mermaid renderer must be lazy-loaded.");
}

for (const marker of ["onetool-admin-root", "OneTool Admin"]) {
  if (!builtHtml.includes(marker)) {
    throw new Error(`Built HTML is missing ${marker}`);
  }
}

const inlineScriptBodies = [...builtHtml.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(
  (match) => match[1],
);
for (const body of inlineScriptBodies) {
  if (/<\/script/i.test(body)) {
    throw new Error("Built HTML contains a raw </script> terminator inside an inline script.");
  }
}

const inlineStyleBodies = [...builtHtml.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)].map(
  (match) => match[1],
);
for (const body of inlineStyleBodies) {
  if (/<\/style/i.test(body)) {
    throw new Error("Built HTML contains a raw </style> terminator inside an inline style.");
  }
}
