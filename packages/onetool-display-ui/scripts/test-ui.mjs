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
  ["codeSplitting: false", "vite.config.ts"],
  ['"dev": "vite"', "package.json"],
  ["@tanstack/react-router", "src/App.tsx"],
  ["@tanstack/react-query", "src/App.tsx"],
  ["@tanstack/react-table", "src/components/PayloadRenderer.tsx"],
  ["/api/display/instances/", "src/api/displayApi.ts"],
  ["@legendapp/list", "src/components/DisplayTimeline.tsx"],
  ["@base-ui/react/popover", "src/components/ui/Popover.tsx"],
  ['style={{ height: "100%", minHeight: 0, overflowY: "auto" }}', "src/components/DisplayTimeline.tsx"],
  ["scroll-bottom-button", "src/components/DisplayTimeline.tsx"],
  ['aria-label="Display message inspector"', "src/App.tsx"],
  ["Open a message in the side panel.", "src/App.tsx"],
  ["store.loadPayload(selectedPanelMessage.id);", "src/App.tsx"],
  ["<MessageRow", "src/App.tsx"],
  ["onToggleRich={togglePanelRich}", "src/App.tsx"],
  ['actionLayout="inspector"', "src/App.tsx"],
  ['aria-label="Resize message inspector"', "src/App.tsx"],
  ['aria-label="Open message in side panel"', "src/components/MessageRow.tsx"],
  ["RenderErrorBoundary", "src/components/MessageRow.tsx"],
  ['className="message-toolbar"', "src/components/MessageRow.tsx"],
  ['className="message-action-menu"', "src/components/MessageRow.tsx"],
  ["Disable rich view", "src/components/MessageRow.tsx"],
  ['layout: "timeline" | "inspector"', "src/components/MessageRow.tsx"],
  ['actionLayout = "timeline"', "src/components/MessageRow.tsx"],
  ['className="file-message-header"', "src/components/MessageRow.tsx"],
  ['className="message-meta"', "src/components/MessageRow.tsx"],
  ["compactMessageId", "src/components/MessageRow.tsx"],
  ['<CopyMessageButton api={api} message={message} payload={payload} kind="content" />', "src/components/MessageRow.tsx"],
  ["api.payload(message.id)", "src/components/MessageRow.tsx"],
  ['kind === "path" ? <FolderTreeIcon', "src/components/MessageRow.tsx"],
  ['status === "failed"', "src/components/MessageRow.tsx"],
  ['className={`icon-button row-action row-open', "src/components/MessageRow.tsx"],
  ["computeStableDisplayRows", "src/lib/displayRows.ts"],
  ["MAX_PAYLOAD_CACHE_ENTRIES", "src/lib/displayStore.ts"],
  ["prunePayloadCache", "src/lib/displayStore.ts"],
  ["store.loadPayload(row.id);", "src/components/DisplayTimeline.tsx"],
  ['className="preview-wrap"', "src/components/MessageRow.tsx"],
  ["react-markdown", "src/components/MarkdownRenderer.tsx"],
  ['className="markdown-viewer"', "src/components/MarkdownRenderer.tsx"],
  ["useDisplaySettings", "src/components/MarkdownRenderer.tsx"],
  ["copyCode = true", "src/components/MarkdownRenderer.tsx"],
  ["@pierre/diffs", "src/lib/diffRendering.ts"],
  ["@pierre/diffs/react", "src/components/CodeView.tsx"],
  ['import("mermaid")', "src/components/MermaidViewer.tsx"],
  ['from "yaml"', "src/components/StructuredDataViewer.tsx"],
  ["StructuredDataViewer", "src/components/PayloadRenderer.tsx"],
  ["showHeader={false}", "src/components/PayloadRenderer.tsx"],
  ['className="plain-text-payload"', "src/components/PayloadRenderer.tsx"],
  ["api.preview(path)", "src/components/PayloadRenderer.tsx"],
  ["MermaidViewer", "src/components/PayloadRenderer.tsx"],
  ["resolveFileViewerKind", "src/components/PayloadRenderer.tsx"],
  ["MAX_GRID_ROWS", "src/components/PayloadRenderer.tsx"],
  ["MAX_GRID_COLUMNS", "src/components/PayloadRenderer.tsx"],
  ['role="grid"', "src/components/PayloadRenderer.tsx"],
  ["resolveDiffThemeName(codeTheme)", "src/components/DiffRenderer.tsx"],
  ['overflow: wrapDiff ? "wrap" : "scroll"', "src/components/DiffRenderer.tsx"],
  ["#onetool-display-root", "src/styles/app.css"],
  [".message-toolbar", "src/styles/app.css"],
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
if (!/\.segmented-control\s*\{[^}]*justify-self:\s*start;/m.test(styles)) {
  throw new Error("Segmented controls must not stretch across structured viewer grids.");
}

const messageRow = await readFile(resolve(root, "src/components/MessageRow.tsx"), "utf8");
if (!/function compactMessageId\(id: string\): string \{\s*return id;\s*\}/m.test(messageRow)) {
  throw new Error("Message row visible IDs must show the full short display ID.");
}
if (!messageRow.includes('return `${hour}:${minute}, ${day}-${months[date.getMonth()]}`;')) {
  throw new Error("Message timestamps must render as HH:mm, dd-Mon.");
}

const copyIndex = messageRow.indexOf('<CopyMessageButton api={api} message={message} payload={payload} kind="content" />');
const panelIndex = messageRow.indexOf("{panelButton}", copyIndex);
const openIndex = messageRow.indexOf("{openButton}", panelIndex);
if (copyIndex < 0 || panelIndex < 0 || openIndex < 0 || copyIndex > panelIndex || panelIndex > openIndex) {
  throw new Error("Timeline actions must render as copy content, side panel, then open.");
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

const payloadRenderer = await readFile(resolve(root, "src/components/PayloadRenderer.tsx"), "utf8");
if (payloadRenderer.includes("Showing {records.length} of {allRecords.length} rows")) {
  throw new Error("Table previews must not render row/column truncation status text.");
}
if (!payloadRenderer.includes("showHeader={false}")) {
  throw new Error("File-backed source renderers must suppress duplicate inner file headers.");
}

for (const marker of ["onetool-display-root", "OneTool Display"]) {
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
