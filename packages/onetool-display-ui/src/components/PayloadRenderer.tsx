import { memo, useEffect, useId, useMemo, useRef, useState } from "react";
import * as YAML from "yaml";
import type { MessageMetadata, PayloadView } from "../types";
import { DiffRenderer } from "./DiffRenderer";
import { MarkdownRenderer } from "./MarkdownRenderer";
import type { DisplayApi } from "../api/displayApi";

const MAX_GRID_ROWS = 200;
const MAX_GRID_COLUMNS = 80;

export const PayloadRenderer = memo(function PayloadRenderer({
  api,
  message,
  payload,
}: {
  api: DisplayApi;
  message: MessageMetadata;
  payload: PayloadView | undefined;
}) {
  if (!payload) return <div className="loading-line">Loading preview...</div>;
  const text = payload.preview?.text ?? stringContent(payload.content);
  if (message.kind === "image" && payload.image_url) {
    return <img className="image-preview" src={payload.image_url} alt={message.title ?? message.id} loading="lazy" />;
  }
  if (message.kind === "markdown") return <MarkdownRenderer text={text} />;
  if (message.kind === "diff" || message.kind === "file_diff") return <DiffRenderer patch={text} />;
  if (message.kind === "json" || message.kind === "yaml" || message.kind === "mermaid" || message.kind === "table") {
    return <StructuredRenderer message={message} text={text} content={payload.content} />;
  }
  if (message.kind === "file") return <FileRenderer message={message} text={text} content={payload.content} />;
  return <CodeLikeRenderer message={message} text={text} />;
});

function FileRenderer({ message, text, content }: { message: MessageMetadata; text: string; content: unknown }) {
  const fileKind = resolveFileViewerKind(message);
  if (fileKind === "markdown") return <MarkdownRenderer text={text} copyCode={false} />;
  if (fileKind === "json") return <MarkdownRenderer text={`\`\`\`json\n${formatJson(content, text)}\n\`\`\``} copyCode={false} />;
  if (fileKind === "yaml") return <MarkdownRenderer text={`\`\`\`yaml\n${formatYaml(content, text)}\n\`\`\``} copyCode={false} />;
  if (fileKind === "code") return <MarkdownRenderer text={`\`\`\`${resolveFileLanguage(message)}\n${text}\n\`\`\``} copyCode={false} />;
  return <pre className="raw-block">{text}</pre>;
}

function CodeLikeRenderer({ message, text }: { message: MessageMetadata; text: string }) {
  if (message.kind === "code") {
    return <MarkdownRenderer text={`\`\`\`${message.payload.language ?? ""}\n${text}\n\`\`\``} copyCode={false} />;
  }
  return <pre className="raw-block">{text}</pre>;
}

function StructuredRenderer({ message, text, content }: { message: MessageMetadata; text: string; content: unknown }) {
  if (message.kind === "table" && Array.isArray(content)) {
    return <DataGridPreview rows={content} />;
  }
  if (message.kind === "json") return <MarkdownRenderer text={`\`\`\`json\n${formatJson(content, text)}\n\`\`\``} />;
  if (message.kind === "yaml") return <MarkdownRenderer text={`\`\`\`yaml\n${formatYaml(content, text)}\n\`\`\``} />;
  if (message.kind === "mermaid") return <MermaidPreview source={text} />;
  return <pre className="raw-block">{text}</pre>;
}

function DataGridPreview({ rows }: { rows: unknown[] }) {
  const allRecords = rows.filter((row): row is Record<string, unknown> => typeof row === "object" && row !== null && !Array.isArray(row));
  const records = allRecords.slice(0, MAX_GRID_ROWS);
  const allColumns = [...new Set(records.flatMap((row) => Object.keys(row)))];
  const columns = allColumns.slice(0, MAX_GRID_COLUMNS);
  if (records.length === 0 || columns.length === 0) return <pre className="raw-block">{JSON.stringify(rows, null, 2)}</pre>;
  const gridTemplateColumns = `repeat(${columns.length}, minmax(140px, 1fr))`;
  return (
    <div className="data-grid-scroller">
      {allRecords.length > records.length || allColumns.length > columns.length ? (
        <p className="muted">Showing {records.length} of {allRecords.length} rows and {columns.length} of {allColumns.length} columns.</p>
      ) : null}
      <div className="data-grid" role="grid" style={{ gridTemplateColumns }}>
        {columns.map((column) => (
          <div key={column} className="data-grid-cell data-grid-header" role="columnheader" title={column}>
            {column}
          </div>
        ))}
        {records.map((row, rowIndex) =>
          columns.map((column) => (
            <div key={`${rowIndex}:${column}`} className="data-grid-cell" role="gridcell" title={formatCell(row[column])}>
              {formatCell(row[column])}
            </div>
          )),
        )}
      </div>
    </div>
  );
}

function MermaidPreview({ source }: { source: string }) {
  const elementId = useId().replace(/:/g, "");
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const diagramSource = useMemo(() => source.trim(), [source]);
  useEffect(() => {
    let cancelled = false;
    const render = async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: resolveMermaidTheme() });
        const { svg } = await mermaid.render(`onetool-display-${elementId}`, diagramSource);
        if (cancelled || !containerRef.current) return;
        containerRef.current.innerHTML = svg;
        setError(null);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    };
    void render();
    return () => {
      cancelled = true;
    };
  }, [diagramSource, elementId]);
  return (
    <div className="mermaid-preview">
      <div ref={containerRef} className="mermaid-canvas" />
      {error ? (
        <>
          <p className="error-text">{error}</p>
          <MarkdownRenderer text={`\`\`\`mermaid\n${diagramSource}\n\`\`\``} />
        </>
      ) : null}
    </div>
  );
}

function stringContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (content === undefined || content === null) return "";
  return JSON.stringify(content, null, 2);
}

function formatJson(content: unknown, text: string): string {
  try {
    return JSON.stringify(typeof content === "string" ? JSON.parse(content) : content, null, 2);
  } catch {
    return text;
  }
}

function formatYaml(content: unknown, text: string): string {
  try {
    const value = typeof content === "string" ? YAML.parse(content) : content;
    return YAML.stringify(value, { indent: 2, lineWidth: 110 }).trimEnd();
  } catch {
    return text;
  }
}

function resolveMermaidTheme(): "default" | "dark" {
  const theme = document.documentElement.dataset.theme;
  if (theme === "light") return "default";
  if (theme === "dark") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "default" : "dark";
}

function formatCell(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null || value === undefined) return "";
  return JSON.stringify(value);
}

function resolveFileViewerKind(message: MessageMetadata): "markdown" | "json" | "yaml" | "code" | "raw" {
  const language = resolveFileLanguage(message);
  if (["markdown", "md", "mdx"].includes(language)) return "markdown";
  if (language === "json") return "json";
  if (["yaml", "yml"].includes(language)) return "yaml";
  if (CODE_LANGUAGES.has(language)) return "code";
  return "raw";
}

function resolveFileLanguage(message: MessageMetadata): string {
  const explicit = normalizeLanguage(message.payload.language);
  if (explicit) return explicit;
  const mime = normalizeMimeLanguage(message.payload.mime_type);
  if (mime) return mime;
  const path = message.payload.path?.toLowerCase() ?? "";
  for (const [extension, language] of FILE_EXTENSION_LANGUAGES) {
    if (path.endsWith(extension)) return language;
  }
  return "text";
}

function normalizeLanguage(value: string | null | undefined): string | null {
  const language = value?.trim().toLowerCase();
  if (!language) return null;
  return LANGUAGE_ALIASES.get(language) ?? language;
}

function normalizeMimeLanguage(value: string | null | undefined): string | null {
  const mime = value?.split(";")[0]?.trim().toLowerCase();
  if (!mime) return null;
  return MIME_LANGUAGES.get(mime) ?? null;
}

const LANGUAGE_ALIASES = new Map([
  ["javascript", "js"],
  ["typescript", "ts"],
  ["python", "py"],
  ["shell", "bash"],
  ["sh", "bash"],
  ["text/markdown", "markdown"],
  ["application/json", "json"],
  ["application/yaml", "yaml"],
  ["text/yaml", "yaml"],
]);

const MIME_LANGUAGES = new Map([
  ["application/json", "json"],
  ["application/x-yaml", "yaml"],
  ["application/yaml", "yaml"],
  ["text/yaml", "yaml"],
  ["text/markdown", "markdown"],
  ["text/x-python", "py"],
  ["application/javascript", "js"],
  ["text/javascript", "js"],
  ["text/typescript", "ts"],
  ["text/x-toml", "toml"],
]);

const FILE_EXTENSION_LANGUAGES: Array<[string, string]> = [
  [".mdx", "mdx"],
  [".md", "markdown"],
  [".markdown", "markdown"],
  [".json", "json"],
  [".yaml", "yaml"],
  [".yml", "yaml"],
  [".py", "py"],
  [".js", "js"],
  [".jsx", "jsx"],
  [".ts", "ts"],
  [".tsx", "tsx"],
  [".toml", "toml"],
  [".rs", "rust"],
  [".go", "go"],
  [".java", "java"],
  [".c", "c"],
  [".h", "c"],
  [".cpp", "cpp"],
  [".hpp", "cpp"],
  [".css", "css"],
  [".scss", "scss"],
  [".html", "html"],
  [".xml", "xml"],
  [".sql", "sql"],
  [".sh", "bash"],
  [".bash", "bash"],
  [".zsh", "bash"],
  [".fish", "fish"],
  [".ini", "ini"],
  [".dockerfile", "dockerfile"],
];

const CODE_LANGUAGES = new Set(FILE_EXTENSION_LANGUAGES.map(([, language]) => language).filter((language) => !["markdown", "mdx", "json", "yaml"].includes(language)));
