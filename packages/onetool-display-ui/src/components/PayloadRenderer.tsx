import { lazy, memo, Suspense, useEffect, useState, type ReactNode } from "react";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable } from "@tanstack/react-table";
import type { MessageMetadata, PayloadView } from "../types";
import { CodeView } from "./CodeView";
import type { DisplayApi } from "../api/displayApi";

const MAX_GRID_ROWS = 200;
const MAX_GRID_COLUMNS = 80;
const LazyDiffRenderer = lazy(() => import("./DiffRenderer").then((module) => ({ default: module.DiffRenderer })));
const LazyMarkdownRenderer = lazy(() => import("./MarkdownRenderer").then((module) => ({ default: module.MarkdownRenderer })));
const LazyMermaidViewer = lazy(() => import("./MermaidViewer").then((module) => ({ default: module.MermaidViewer })));
const LazyStructuredDataViewer = lazy(() => import("./StructuredDataViewer").then((module) => ({ default: module.StructuredDataViewer })));

export const PayloadRenderer = memo(function PayloadRenderer({
  api,
  message,
  payload,
  rich = true,
}: {
  api: DisplayApi;
  message: MessageMetadata;
  payload: PayloadView | undefined;
  rich?: boolean;
}) {
  if (!payload) return <div className="loading-line">Loading preview...</div>;
  const text = payload.preview?.text ?? stringContent(payload.content);
  if (!rich) return <pre className="raw-block">{text}</pre>;
  if (message.kind === "image" && payload.image_url) {
    return <img className="image-preview" src={payload.image_url} alt={messageTitle(message) ?? message.id} loading="lazy" />;
  }
  if (message.kind === "markdown") return <LazyRenderer><LazyMarkdownRenderer text={text} /></LazyRenderer>;
  if (message.kind === "diff" || message.kind === "file_diff") return <LazyRenderer><LazyDiffRenderer patch={text} /></LazyRenderer>;
  if (message.kind === "json" || message.kind === "yaml" || message.kind === "mermaid" || message.kind === "table") {
    return <StructuredRenderer message={message} text={text} content={payload.content} />;
  }
  if (message.kind === "file") return <FileRenderer api={api} message={message} text={text} content={payload.content} />;
  if (message.kind === "text") return <PlainTextRenderer text={text} />;
  return <CodeLikeRenderer message={message} text={text} />;
});

function PlainTextRenderer({ text }: { text: string }) {
  return <div className="plain-text-payload">{text}</div>;
}

function FileRenderer({ api, message, text, content }: { api: DisplayApi; message: MessageMetadata; text: string; content: unknown }) {
  const fileKind = resolveFileViewerKind(message);
  const previewText = useFilePreviewText(api, message, text);
  if (fileKind === "markdown") return <LazyRenderer><LazyMarkdownRenderer text={previewText} copyCode={false} /></LazyRenderer>;
  if (fileKind === "json" || fileKind === "yaml") {
    return (
      <LazyRenderer>
        <LazyStructuredDataViewer kind={fileKind} text={previewText} content={content} name={fileName(message.payload.path)} showHeader={false} />
      </LazyRenderer>
    );
  }
  if (fileKind === "code") return <CodeView text={previewText} language={resolveFileLanguage(message)} name={fileName(message.payload.path)} showHeader={false} />;
  return <pre className="raw-block">{previewText}</pre>;
}

function CodeLikeRenderer({ message, text }: { message: MessageMetadata; text: string }) {
  if (message.kind === "code") {
    return <CodeView text={text} language={message.payload.language} name={messageTitle(message) ?? fileName(message.payload.path)} showHeader={!message.payload.path} />;
  }
  return <pre className="raw-block">{text}</pre>;
}

function messageTitle(message: MessageMetadata): string | null {
  return message.metadata.title || null;
}

function StructuredRenderer({ message, text, content }: { message: MessageMetadata; text: string; content: unknown }) {
  if (message.kind === "table" && Array.isArray(content)) {
    return <DataGridPreview rows={content} />;
  }
  if (message.kind === "json" || message.kind === "yaml") {
    return <LazyRenderer><LazyStructuredDataViewer kind={message.kind} text={text} content={content} /></LazyRenderer>;
  }
  if (message.kind === "mermaid") return <LazyRenderer><LazyMermaidViewer source={text} /></LazyRenderer>;
  return <pre className="raw-block">{text}</pre>;
}

function LazyRenderer({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="loading-line">Loading renderer...</div>}>{children}</Suspense>;
}

function DataGridPreview({ rows }: { rows: unknown[] }) {
  const allRecords = rows.filter((row): row is Record<string, unknown> => typeof row === "object" && row !== null && !Array.isArray(row));
  const records = allRecords.slice(0, MAX_GRID_ROWS);
  const allColumns = [...new Set(records.flatMap((row) => Object.keys(row)))];
  const columns = allColumns.slice(0, MAX_GRID_COLUMNS);
  const columnHelper = createColumnHelper<Record<string, unknown>>();
  const table = useReactTable({
    data: records,
    columns: columns.map((column) =>
      columnHelper.accessor((row) => row[column], {
        id: column,
        header: column,
        cell: (info) => formatCell(info.getValue()),
      }),
    ),
    getCoreRowModel: getCoreRowModel(),
  });
  if (records.length === 0 || columns.length === 0) return <pre className="raw-block">{JSON.stringify(rows, null, 2)}</pre>;
  const gridTemplateColumns = `repeat(${columns.length}, minmax(140px, 1fr))`;
  return (
    <div className="data-grid-scroller">
      <div className="data-grid" role="grid" style={{ gridTemplateColumns }}>
        {table.getHeaderGroups().flatMap((headerGroup) =>
          headerGroup.headers.map((header) => (
            <div key={header.id} className="data-grid-cell data-grid-header" role="columnheader" title={String(header.column.columnDef.header)}>
              {flexRender(header.column.columnDef.header, header.getContext())}
            </div>
          )),
        )}
        {table.getRowModel().rows.flatMap((row) =>
          row.getVisibleCells().map((cell) => (
            <div key={cell.id} className="data-grid-cell" role="gridcell" title={formatCell(cell.getValue())}>
              {flexRender(cell.column.columnDef.cell, cell.getContext())}
            </div>
          )),
        )}
      </div>
    </div>
  );
}

function stringContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (content === undefined || content === null) return "";
  return JSON.stringify(content, null, 2);
}

function formatCell(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null || value === undefined) return "";
  return JSON.stringify(value);
}

function useFilePreviewText(api: DisplayApi, message: MessageMetadata, fallbackText: string): string {
  const [previewText, setPreviewText] = useState<string | null>(null);
  const path = message.payload.path;
  useEffect(() => {
    let cancelled = false;
    setPreviewText(null);
    if (!path || fallbackText) return;
    void api.preview(path).then((preview) => {
      if (!cancelled) setPreviewText(preview.text);
    }).catch(() => {
      if (!cancelled) setPreviewText("");
    });
    return () => {
      cancelled = true;
    };
  }, [api, fallbackText, path]);
  return previewText ?? fallbackText;
}

function fileName(path: string | null | undefined): string | null {
  if (!path) return null;
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? path;
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
