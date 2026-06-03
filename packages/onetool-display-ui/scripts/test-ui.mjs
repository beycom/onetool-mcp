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
  ["@legendapp/list", "src/components/DisplayTimeline.tsx"],
  ["@base-ui/react/popover", "src/components/ui/Popover.tsx"],
  ['style={{ height: "100%", minHeight: 0, overflowY: "auto" }}', "src/components/DisplayTimeline.tsx"],
  ['querySelector(`[data-message-id="${CSS.escape(id)}"]`)', "src/components/DisplayTimeline.tsx"],
  ['aria-label="Display message inspector"', "src/App.tsx"],
  ["Open a message in the side panel.", "src/App.tsx"],
  ["store.loadPayload(id);\n  }, [store]);", "src/App.tsx"],
  ["<PayloadRenderer api={store.api} message={selectedPanelMessage}", "src/App.tsx"],
  ['aria-label="Resize message inspector"', "src/App.tsx"],
  ["MessageActions api={store.api}", "src/App.tsx"],
  ['aria-label="Open message in side panel"', "src/components/MessageRow.tsx"],
  ['className="message-toolbar"', "src/components/MessageRow.tsx"],
  ['className="preview-toggle"', "src/components/MessageRow.tsx"],
  ['className="message-meta"', "src/components/MessageRow.tsx"],
  ["api.payload(message.id)", "src/components/MessageRow.tsx"],
  ['kind === "path" ? <FileTextIcon', "src/components/MessageRow.tsx"],
  ['status === "failed"', "src/components/MessageRow.tsx"],
  ["computeStableDisplayRows", "src/lib/displayRows.ts"],
  ["MAX_PAYLOAD_CACHE_ENTRIES", "src/lib/displayStore.ts"],
  ["prunePayloadCache", "src/lib/displayStore.ts"],
  ["for (const id of expandedIds) loadPayload(id)", "src/lib/displayStore.ts"],
  ["if (previewLines <= 1) return false", "src/lib/displayStore.ts"],
  ["react-markdown", "src/components/MarkdownRenderer.tsx"],
  ["useDisplaySettings", "src/components/MarkdownRenderer.tsx"],
  ["copyCode = true", "src/components/MarkdownRenderer.tsx"],
  ["@pierre/diffs", "src/lib/diffRendering.ts"],
  ['import("mermaid")', "src/components/PayloadRenderer.tsx"],
  ['from "yaml"', "src/components/PayloadRenderer.tsx"],
  ["resolveFileViewerKind", "src/components/PayloadRenderer.tsx"],
  ["MAX_GRID_ROWS", "src/components/PayloadRenderer.tsx"],
  ["MAX_GRID_COLUMNS", "src/components/PayloadRenderer.tsx"],
  ['role="grid"', "src/components/PayloadRenderer.tsx"],
  ["resolveDiffThemeName(codeTheme)", "src/components/DiffRenderer.tsx"],
  ['overflow: wrapDiff ? "wrap" : "scroll"', "src/components/DiffRenderer.tsx"],
  ["#onetool-display-root", "src/styles/app.css"],
  [".message-toolbar", "src/styles/app.css"],
  ["left: 18px;", "src/styles/app.css"],
  [".message-meta", "src/styles/app.css"],
  ["--side-panel-width", "src/styles/app.css"],
  [".inspector-payload .shiki-block pre", "src/styles/app.css"],
];

for (const [needle, file] of sourceChecks) {
  const content = await readFile(resolve(root, file), "utf8");
  if (!content.includes(needle)) {
    throw new Error(`${file} is missing expected t3code-derived marker ${needle}`);
  }
}

for (const marker of ["onetool-display-root", "OneTool Display"]) {
  if (!builtHtml.includes(marker)) {
    throw new Error(`Built HTML is missing ${marker}`);
  }
}
