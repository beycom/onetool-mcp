import { useCallback, useMemo, useState } from "react";
import { DisplayApi } from "../api";
import type { DisplayStore } from "./displayStore";
import type { MessageMetadata, PayloadView } from "../types";

const MOCK_NOW = Date.parse("2026-06-02T09:20:00+10:00");
const ACTIVE_ID = "mock-active-target";

interface MockMessage {
  metadata: MessageMetadata;
  payload: PayloadView;
}

export function useMockDisplayStore(location: Location): DisplayStore {
  const api = useMemo(() => {
    const mockApi = new DisplayApi(location, "mock-active-target");
    mockApi.open = async (path: string) => ({ status: "mock", opened: true, path });
    return mockApi;
  }, [location]);
  const fixtures = useMemo(() => buildMockMessages(), []);
  const [selectedId, setSelectedId] = useState<string | null>(ACTIVE_ID);
  const [payloadById, setPayloadById] = useState<ReadonlyMap<string, PayloadView>>(() => new Map());

  const byId = useMemo(() => new Map(fixtures.map((entry) => [entry.metadata.id, entry.payload])), [fixtures]);
  const messages = useMemo(() => fixtures.map((entry) => entry.metadata), [fixtures]);

  const refresh = useCallback(async () => undefined, []);
  const loadPayload = useCallback((id: string) => {
    setPayloadById((current) => {
      if (current.has(id)) return current;
      const payload = byId.get(id);
      return payload ? new Map(current).set(id, payload) : current;
    });
  }, [byId]);
  const focusMessage = useCallback((id: string) => {
    setSelectedId(id);
    setPayloadById((current) => {
      if (current.has(id)) return current;
      const payload = byId.get(id);
      return payload ? new Map(current).set(id, payload) : current;
    });
  }, [byId]);

  return { api, messages, selectedId, payloadById, error: null, refresh, loadPayload, focusMessage };
}

function buildMockMessages(): MockMessage[] {
  const rows: MockMessage[] = [];
  for (let index = 1; index <= 100; index += 1) {
    rows.push(message({
      id: `mock-text-${index.toString().padStart(3, "0")}`,
      kind: "text",
      title: `agent.log line ${index.toString().padStart(3, "0")}`,
      summary: `Planner updated artifact queue shard ${index % 12} after validating cached handle ctx_${(1460 + index).toString(16)}.`,
      content: `09:${(index % 60).toString().padStart(2, "0")}:18.44 agent.log [display] row=${index} status=ready message="Planner updated artifact queue shard ${index % 12} after validating cached handle ctx_${(1460 + index).toString(16)}."`,
      sizeOffset: index,
    }));
  }
  rows.push(
    message({
      id: "mock-markdown-large",
      kind: "markdown",
      title: "artifact-notes.md",
      summary: "Large markdown payload with GFM table, task list, code fences, and operational notes.",
      content: largeMarkdown(),
      language: "markdown",
    }),
    message({
      id: "mock-code-tsx",
      kind: "code",
      title: "ArtifactTimeline.tsx",
      summary: "Large TSX payload showing virtual rows, bounded payload panels, and action handlers.",
      content: largeTsx(),
      language: "tsx",
    }),
    message({
      id: "mock-code-python",
      kind: "code",
      title: "artifact_ingest.py",
      summary: "Large Python payload with parsing, validation, and event fan-out.",
      content: largePython(),
      language: "python",
    }),
    message({
      id: "mock-unified-diff",
      kind: "diff",
      title: "display timeline patch",
      summary: "Unified diff rendered through @pierre/diffs FileDiff.",
      content: unifiedDiff(),
      language: "diff",
    }),
    message({
      id: "mock-json-nested",
      kind: "json",
      title: "run-result.json",
      summary: "Nested JSON result with tool calls, artifacts, timings, and provenance.",
      content: nestedJson(),
      language: "json",
    }),
    message({
      id: "mock-yaml-config",
      kind: "yaml",
      title: "display.yaml",
      summary: "YAML configuration payload for display service policies and retention.",
      content: yamlConfig(),
      language: "yaml",
    }),
    message({
      id: "mock-mermaid-flow",
      kind: "mermaid",
      title: "artifact-flow.mmd",
      summary: "Mermaid flowchart source payload for artifact lifecycle.",
      content: mermaidFlow(),
      language: "mermaid",
    }),
    message({
      id: "mock-wide-metrics",
      kind: "table",
      title: "wide-metrics.csv",
      summary: "Wide metrics table with 100 rows and 35 columns.",
      content: buildWideMetricsTable(),
    }),
    message({
      id: "mock-tall-events",
      kind: "table",
      title: "event-stream.csv",
      summary: "Tall event table with 260 rows.",
      content: buildTallEventTable(),
    }),
    ...filePreviewMessages(),
    message({
      id: "mock-file-diff-preview",
      kind: "file_diff",
      title: "src/display/service.py",
      summary: "File diff preview for service-side payload references.",
      content: fileDiffPreview(),
      path: "/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp/src/ot/display/service.py",
      language: "diff",
    }),
    message({
      id: ACTIVE_ID,
      kind: "markdown",
      title: "active-target.md",
      summary: "Focused row selected by the mock event stream; expand to inspect the final target payload.",
      content: activeTargetMarkdown(),
      language: "markdown",
      sizeOffset: 999,
    }),
  );
  return rows;
}

function message({
  id,
  kind,
  title,
  summary,
  content,
  language,
  path,
  sizeOffset = 0,
}: {
  id: string;
  kind: MessageMetadata["kind"];
  title: string;
  summary: string;
  content: unknown;
  language?: string;
  path?: string;
  sizeOffset?: number;
}): MockMessage {
  const text = stringify(content);
  const createdAt = new Date(MOCK_NOW + sizeOffset * 1000).toISOString();
  const metadata: MessageMetadata = {
    id,
    kind,
    metadata: {
      source: "mock.artifacts",
      title,
      summary,
    },
    preview_lines: countLines(text),
    created_at: createdAt,
    updated_at: createdAt,
    payload: {
      mode: kind === "file_diff" ? "file_diff" : path ? "file" : "inline",
      size_bytes: new TextEncoder().encode(text).length,
      path: path ?? null,
      language: language ?? null,
      mime_type: null,
    },
    status: "ready",
  };
  return {
    metadata,
    payload: {
      metadata,
      preview: { text, truncated: false, size_bytes: metadata.payload.size_bytes, limit_bytes: metadata.payload.size_bytes },
      content,
      open_url: path ? `/mock/open?path=${encodeURIComponent(path)}` : null,
    },
  };
}

function stringify(content: unknown): string {
  if (typeof content === "string") return content;
  return JSON.stringify(content, null, 2);
}

function countLines(text: string): number {
  return text === "" ? 0 : text.split(/\r?\n/).length;
}

function largeMarkdown(): string {
  return `# Artifact Render Audit

## Scope

This payload verifies that markdown content can be expanded inside a bounded row without moving the rest of the app shell. It includes headings, GFM tables, task lists, fenced code, and long notes.

### Checklist

- [x] Keep rows collapsed until requested
- [x] Lazy-load payloads after expansion
- [x] Keep code blocks copyable
- [ ] Attach live service metrics when API data is available

| Artifact | Kind | Rows | Risk | Owner |
| --- | --- | ---: | --- | --- |
| Markdown notes | markdown | 1 | medium | display |
| Wide metrics | table | 100 | high | telemetry |
| Tall events | table | 260 | high | runtime |
| Unified diff | diff | 1 | medium | review |

\`\`\`tsx
export function CompactRow({ title, selected }: { title: string; selected: boolean }) {
  return <button data-selected={selected}>{title}</button>;
}
\`\`\`

\`\`\`python
def bounded_preview(text: str, limit: int = 12000) -> str:
    return text if len(text) <= limit else text[:limit]
\`\`\`

## Notes

${Array.from({ length: 36 }, (_, index) => `${index + 1}. Long note ${index + 1}: the renderer should preserve readable spacing while avoiding any payload height that pushes the timeline outside the first viewport. The row remains part of the virtualized list and scroll position should stay predictable after expansion.`).join("\n")}
`;
}

function largeTsx(): string {
  return `import { memo, useCallback, useMemo, useState } from "react";
import { CopyIcon, Rows3Icon } from "lucide-react";

type ArtifactKind = "markdown" | "code" | "diff" | "table" | "file";

interface ArtifactRow {
  id: string;
  kind: ArtifactKind;
  title: string;
  sizeBytes: number;
  selected: boolean;
}

export const ArtifactTimeline = memo(function ArtifactTimeline({ rows }: { rows: ArtifactRow[] }) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set());
  const visible = useMemo(() => rows.filter((row) => row.sizeBytes > 0), [rows]);
  const toggle = useCallback((id: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return (
    <section aria-label="Artifact timeline">
      {visible.map((row) => (
        <article key={row.id} className={row.selected ? "message-row selected" : "message-row"}>
          <button type="button" onClick={() => toggle(row.id)} className="row-header">
            <Rows3Icon size={16} />
            <span>{row.kind}</span>
            <span>{row.title}</span>
            <span>{row.sizeBytes.toLocaleString()} B</span>
          </button>
          {expanded.has(row.id) ? <PayloadPreview id={row.id} /> : null}
        </article>
      ))}
    </section>
  );
});

${Array.from({ length: 42 }, (_, index) => `function PayloadLine${index + 1}() {
  return <pre>{JSON.stringify({ step: ${index + 1}, status: "ready", shard: "display-${index % 6}" }, null, 2)}</pre>;
}`).join("\n\n")}

function PayloadPreview({ id }: { id: string }) {
  return (
    <div className="payload-panel">
      <button type="button" aria-label="Copy code"><CopyIcon size={14} /></button>
      <pre>{id}</pre>
    </div>
  );
}
`;
}

function largePython(): string {
  return `from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ArtifactRecord:
    id: str
    kind: str
    title: str
    payload_path: Path | None
    size_bytes: int


class ArtifactIngestor:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.records: dict[str, ArtifactRecord] = {}

    def ingest_many(self, rows: Iterable[Mapping[str, object]]) -> list[ArtifactRecord]:
        accepted: list[ArtifactRecord] = []
        for raw in rows:
            record = self._coerce(raw)
            self.records[record.id] = record
            accepted.append(record)
        return accepted

    def _coerce(self, raw: Mapping[str, object]) -> ArtifactRecord:
        artifact_id = str(raw["id"])
        payload = raw.get("payload_path")
        return ArtifactRecord(
            id=artifact_id,
            kind=str(raw["kind"]),
            title=str(raw.get("title") or artifact_id),
            payload_path=self.root / str(payload) if payload else None,
            size_bytes=int(raw.get("size_bytes") or 0),
        )


${Array.from({ length: 58 }, (_, index) => `def validate_stage_${index + 1}(record: ArtifactRecord) -> tuple[bool, str]:
    if record.size_bytes <= ${index}:
        return False, "payload too small for validation stage ${index + 1}"
    if not record.title.strip():
        return False, "missing title at validation stage ${index + 1}"
    return True, "ready"`).join("\n\n")}
`;
}

function unifiedDiff(): string {
  return `diff --git a/packages/admin-ui/src/features/display/components/MessageRow.tsx b/packages/admin-ui/src/features/display/components/MessageRow.tsx
index 15f4e29..93a7a91 100644
--- a/packages/admin-ui/src/features/display/components/MessageRow.tsx
+++ b/packages/admin-ui/src/features/display/components/MessageRow.tsx
@@ -1,8 +1,10 @@
 import { ChevronDownIcon, ChevronRightIcon } from "lucide-react";
 import { memo } from "react";
 import type { MessageMetadata, PayloadView } from "../types";
+import { PayloadRenderer } from "./PayloadRenderer";
 
 export const MessageRow = memo(function MessageRow({
   message,
   expanded,
+  selected,
   payload,
 }) {
@@ -14,7 +16,7 @@ export const MessageRow = memo(function MessageRow({
-  return <article className="message-row">
+  return <article className={selected ? "message-row selected" : "message-row"}>
     <button type="button" className="row-header" aria-expanded={expanded}>
       {expanded ? <ChevronDownIcon size={16} /> : <ChevronRightIcon size={16} />}
       <span>{message.kind}</span>
@@ -28,3 +30,18 @@ export const MessageRow = memo(function MessageRow({
   );
 });
+
+function formatSize(bytes: number): string {
+  if (bytes < 1024) return \`\${bytes} B\`;
+  return \`\${(bytes / 1024).toFixed(1)} KB\`;
+}
diff --git a/packages/admin-ui/src/styles/app.css b/packages/admin-ui/src/styles/app.css
index fdc5321..c832f08 100644
--- a/packages/admin-ui/src/styles/app.css
+++ b/packages/admin-ui/src/styles/app.css
@@ -55,6 +55,11 @@ body {
 .message-row.selected {
   border-color: var(--accent);
 }
+
+.payload-panel {
+  max-height: 76vh;
+  overflow: auto;
+}
`;
}

function nestedJson(): Record<string, unknown> {
  return {
    run_id: "run_01HZQC7DF6Z9V9G9AP3AGT0K1J",
    status: "complete",
    focus: ACTIVE_ID,
    timings_ms: { queued: 18, hydrate: 126, render: 42, total: 1184 },
    artifacts: Array.from({ length: 12 }, (_, index) => ({
      id: `artifact_${index + 1}`,
      kind: ["markdown", "code", "table", "diff"][index % 4],
      provenance: {
        tool: ["display.write", "ctx.append", "ot.run"][index % 3],
        span: `display.render.${index + 1}`,
        inputs: { session: "local-dev", shard: index % 4, retry: false },
      },
      payload: {
        storage: { mode: index % 3 === 0 ? "file" : "inline", checksum: `sha256:${(index + 1).toString(16).padStart(64, "0")}` },
        preview: { truncated: false, lines: 20 + index * 7 },
      },
    })),
  };
}

function yamlConfig(): string {
  return `display:
  theme: dark
  density: compact
  polling:
    interval_ms: 900
    backoff_ms: [900, 1200, 1800, 2500]
  payloads:
    lazy_load: true
    preview_limit_bytes: 65536
    max_panel_height: 76vh
  retention:
    max_messages: 5000
    max_payload_mb: 256
  renderers:
    markdown:
      gfm: true
      copy_code: true
    diff:
      provider: "@pierre/diffs"
      theme: dark
    tables:
      sticky_header: true
      horizontal_scroll: true
      vertical_scroll: true
sources:
  - name: local-service
    instance: dev-panel
    trusted: true
  - name: artifact-cache
    path: .onetool/display
    trusted: true
`;
}

function mermaidFlow(): string {
  return `flowchart TD
  A[Tool emits artifact] --> B{Payload size}
  B -->|small| C[Inline preview]
  B -->|large| D[File-backed payload]
  C --> E[Message metadata]
  D --> E
  E --> F[Virtual timeline row]
  F --> G{Expanded?}
  G -->|no| H[Compact summary]
  G -->|yes| I[Lazy payload load]
  I --> J[Renderer selection]
  J --> K[Markdown]
  J --> L[Code]
  J --> M[Diff via @pierre/diffs]
  J --> N[Scrollable table]
  M --> O[Focused active target]
  N --> O
`;
}

function buildWideMetricsTable(): Record<string, unknown>[] {
  const columns = Array.from({ length: 35 }, (_, index) => `metric_${(index + 1).toString().padStart(2, "0")}`);
  return Array.from({ length: 100 }, (_, rowIndex) => {
    const row: Record<string, unknown> = {
      row: rowIndex + 1,
      shard: `display-${rowIndex % 8}`,
      timestamp: new Date(MOCK_NOW + rowIndex * 15000).toISOString(),
    };
    for (const [columnIndex, column] of columns.entries()) {
      row[column] = Number(((rowIndex + 1) * (columnIndex + 3) / 17).toFixed(3));
    }
    return row;
  });
}

function buildTallEventTable(): Record<string, unknown>[] {
  return Array.from({ length: 260 }, (_, index) => ({
    seq: index + 1,
    time: new Date(MOCK_NOW + index * 1750).toISOString(),
    event: ["message", "payload_ready", "focus", "cache_hit", "render_complete"][index % 5],
    id: `mock-${(index % 118) + 1}`,
    latency_ms: 12 + (index * 19) % 230,
    worker: `ui-${index % 6}`,
    notes: `event ${index + 1} processed with viewport shard ${index % 4}`,
  }));
}

function filePreviewMessages(): MockMessage[] {
  return [
    message({
      id: "mock-file-readme",
      kind: "file",
      title: "README.md preview",
      summary: "File preview row for a markdown document.",
      path: "/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp/README.md",
      language: "markdown",
      content: "# OneTool MCP\n\nLocal tool orchestration with display artifacts, context handles, and developer utilities.\n\n## Preview\n\nThis file row keeps path actions visible and renders the bounded file preview below.",
    }),
    message({
      id: "mock-file-config",
      kind: "file",
      title: "pyproject.toml preview",
      summary: "File preview row for project configuration.",
      path: "/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp/pyproject.toml",
      language: "toml",
      content: "[project]\nname = \"onetool-mcp\"\nrequires-python = \">=3.12\"\n\n[tool.pytest.ini_options]\nmarkers = [\"smoke\", \"unit\", \"integration\", \"slow\", \"core\", \"tools\"]",
    }),
    message({
      id: "mock-file-log",
      kind: "file",
      title: "display-session.log preview",
      summary: "File preview row for runtime log output.",
      path: "/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp/.onetool/display/session.log",
      language: "log",
      content: Array.from({ length: 28 }, (_, index) => `2026-06-02T09:${(20 + index).toString().padStart(2, "0")}:02+10:00 display INFO persisted artifact id=mock-${index + 1} bytes=${1024 + index * 139}`).join("\n"),
    }),
  ];
}

function fileDiffPreview(): string {
  return `diff --git a/src/ot/display/service.py b/src/ot/display/service.py
index 7d419ca..e9ac5b1 100644
--- a/src/ot/display/service.py
+++ b/src/ot/display/service.py
@@ -42,7 +42,11 @@ class DisplayService:
     def write(self, message: DisplayMessage) -> DisplayMessage:
         self._store.append(message)
         self._events.publish({"type": "message", "id": message.id})
-        return message
+        if message.focus:
+            self._events.publish({"type": "focus", "id": message.id})
+        return self._store.read(message.id)
 
     def payload(self, message_id: str) -> PayloadView:
         return self._store.payload(message_id)
`;
}

function activeTargetMarkdown(): string {
  return `# Active Target

This final focused row is selected by default and scrolls into view when the mock timeline mounts.

- status: ready
- renderer: markdown
- selection: active
- expected behavior: clear border, compact row header, bounded expanded payload

\`\`\`json
{
  "active": true,
  "message_id": "${ACTIVE_ID}",
  "viewport": "scrolled-into-view"
}
\`\`\`
`;
}
