import { ChevronDownIcon, ChevronRightIcon } from "lucide-react";
import { memo, useMemo, useState, type CSSProperties, type KeyboardEvent } from "react";
import * as YAML from "yaml";
import { CodeView } from "./CodeView";

export const STRUCTURED_SOURCE_LIMIT_BYTES = 256 * 1024;
export const STRUCTURED_MAX_DEPTH = 12;
export const STRUCTURED_MAX_SIBLINGS = 200;

export const StructuredDataViewer = memo(function StructuredDataViewer({
  kind,
  text,
  content,
  name,
  showHeader = true,
}: {
  kind: "json" | "yaml";
  text: string;
  content: unknown;
  name?: string | null;
  showHeader?: boolean;
}) {
  const parsed = useMemo(() => parseStructuredValue(kind, content, text), [content, kind, text]);
  const [view, setView] = useState<"tree" | "source">("tree");
  return (
    <div className="structured-viewer">
      <SegmentedControl value={view} options={["tree", "source"]} onChange={setView} />
      <div className="structured-body">
        {view === "tree" ? (
          <div className="tree-viewer">
            {parsed.truncated ? (
              <CodeView text={parsed.source} language={kind} name={name ?? `artifact.${kind}`} showHeader={showHeader} />
            ) : (
              <TreeNode name="root" value={parsed.value} depth={0} defaultOpen />
            )}
          </div>
        ) : (
          <CodeView text={parsed.source} language={kind} name={name ?? `artifact.${kind}`} showHeader={showHeader} />
        )}
      </div>
    </div>
  );
});

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: T[];
  onChange: (value: T) => void;
}) {
  const selectedIndex = options.indexOf(value);
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    let nextIndex: number | null = null;
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") nextIndex = Math.max(0, selectedIndex - 1);
    if (event.key === "ArrowRight" || event.key === "ArrowDown") nextIndex = Math.min(options.length - 1, selectedIndex + 1);
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = options.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    onChange(options[nextIndex]);
  };
  return (
    <div className="segmented-control" role="tablist" aria-label="Structured data view" onKeyDown={onKeyDown}>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          className={value === option ? "active" : ""}
          role="tab"
          aria-selected={value === option}
          tabIndex={value === option ? 0 : -1}
          onClick={() => onChange(option)}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

function TreeNode({ name, value, depth, defaultOpen = false }: { name: string; value: unknown; depth: number; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen || depth < 2);
  const expandable = Array.isArray(value) || (typeof value === "object" && value !== null);
  if (depth >= STRUCTURED_MAX_DEPTH && expandable) {
    return (
      <div className="tree-row" style={{ "--tree-depth": depth } as CSSProperties}>
        <span className="tree-key">{name}</span>
        <span className="tree-value">(max depth reached)</span>
      </div>
    );
  }
  if (!expandable) {
    return (
      <div className="tree-row" style={{ "--tree-depth": depth } as CSSProperties}>
        <span className="tree-key">{name}</span>
        <span className="tree-value">{formatPrimitive(value)}</span>
      </div>
    );
  }
  const allEntries = Array.isArray(value) ? value.map((item, index) => [String(index), item] as const) : Object.entries(value as Record<string, unknown>);
  const entries: Array<readonly [string, unknown]> = allEntries.slice(0, STRUCTURED_MAX_SIBLINGS);
  return (
    <div>
      <button type="button" className="tree-row tree-toggle" style={{ "--tree-depth": depth } as CSSProperties} aria-expanded={open} onClick={() => setOpen((next) => !next)}>
        {open ? <ChevronDownIcon size={14} /> : <ChevronRightIcon size={14} />}
        <span className="tree-key">{name}</span>
        <span className="tree-summary">{Array.isArray(value) ? `Array(${allEntries.length})` : `Object(${allEntries.length})`}</span>
      </button>
      {open ? (
        <>
          {entries.map(([key, entryValue]) => <TreeNode key={key} name={key} value={entryValue} depth={depth + 1} />)}
          {allEntries.length > entries.length ? (
            <div className="tree-row" style={{ "--tree-depth": depth + 1 } as CSSProperties}>
              <span className="tree-value">{allEntries.length - entries.length} more entries hidden</span>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export function parseStructuredValue(kind: "json" | "yaml", content: unknown, text: string): { value: unknown; source: string; truncated: boolean } {
  const sourceText = typeof text === "string" ? text : "";
  if (byteLength(sourceText) > STRUCTURED_SOURCE_LIMIT_BYTES) {
    return { value: sourceText, source: sourceText, truncated: true };
  }
  try {
    const rawValue = content === undefined || content === null ? sourceText : content;
    const value: unknown = typeof rawValue === "string" ? (kind === "json" ? JSON.parse(rawValue) as unknown : YAML.parse(rawValue) as unknown) : rawValue;
    const boundedValue = boundStructuredValue(value, 0);
    return {
      value: boundedValue,
      source: kind === "json" ? JSON.stringify(boundedValue, null, 2) : YAML.stringify(boundedValue, { indent: 2, lineWidth: 110 }).trimEnd(),
      truncated: false,
    };
  } catch {
    return { value: sourceText || "(empty)", source: sourceText, truncated: false };
  }
}

function formatPrimitive(value: unknown): string {
  if (typeof value === "string") return JSON.stringify(value);
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  return String(value);
}

function boundStructuredValue(value: unknown, depth: number): unknown {
  if (depth >= STRUCTURED_MAX_DEPTH) return "(max depth reached)";
  if (Array.isArray(value)) {
    return value.slice(0, STRUCTURED_MAX_SIBLINGS).map((item) => boundStructuredValue(item, depth + 1));
  }
  if (typeof value !== "object" || value === null) return value;
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>)
      .slice(0, STRUCTURED_MAX_SIBLINGS)
      .map(([key, item]) => [key, boundStructuredValue(item, depth + 1)]),
  );
}

function byteLength(value: string): number {
  return new TextEncoder().encode(value).length;
}
