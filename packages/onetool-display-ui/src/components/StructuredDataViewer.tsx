import { ChevronDownIcon, ChevronRightIcon } from "lucide-react";
import { memo, useMemo, useState, type CSSProperties } from "react";
import * as YAML from "yaml";
import { CodeView } from "./CodeView";

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
            <TreeNode name="root" value={parsed.value} depth={0} defaultOpen />
          </div>
        ) : (
          <CodeView text={parsed.source} language={kind} name={name ?? `artifact.${kind}`} showHeader={showHeader} />
        )}
      </div>
    </div>
  );
});

function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: T[];
  onChange: (value: T) => void;
}) {
  return (
    <div className="segmented-control">
      {options.map((option) => (
        <button key={option} type="button" className={value === option ? "active" : ""} onClick={() => onChange(option)}>
          {option}
        </button>
      ))}
    </div>
  );
}

function TreeNode({ name, value, depth, defaultOpen = false }: { name: string; value: unknown; depth: number; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen || depth < 2);
  const expandable = Array.isArray(value) || (typeof value === "object" && value !== null);
  if (!expandable) {
    return (
      <div className="tree-row" style={{ "--tree-depth": depth } as CSSProperties}>
        <span className="tree-key">{name}</span>
        <span className="tree-value">{formatPrimitive(value)}</span>
      </div>
    );
  }
  const entries = Array.isArray(value) ? value.map((item, index) => [String(index), item] as const) : Object.entries(value as Record<string, unknown>);
  return (
    <div>
      <button type="button" className="tree-row tree-toggle" style={{ "--tree-depth": depth } as CSSProperties} onClick={() => setOpen((next) => !next)}>
        {open ? <ChevronDownIcon size={14} /> : <ChevronRightIcon size={14} />}
        <span className="tree-key">{name}</span>
        <span className="tree-summary">{Array.isArray(value) ? `Array(${entries.length})` : `Object(${entries.length})`}</span>
      </button>
      {open ? entries.map(([key, entryValue]) => <TreeNode key={key} name={key} value={entryValue} depth={depth + 1} />) : null}
    </div>
  );
}

function parseStructuredValue(kind: "json" | "yaml", content: unknown, text: string): { value: unknown; source: string } {
  const sourceText = typeof text === "string" ? text : "";
  try {
    const rawValue = content === undefined || content === null ? sourceText : content;
    const value = typeof rawValue === "string" ? (kind === "json" ? JSON.parse(rawValue) : YAML.parse(rawValue)) : rawValue;
    return {
      value,
      source: kind === "json" ? JSON.stringify(value, null, 2) : YAML.stringify(value, { indent: 2, lineWidth: 110 }).trimEnd(),
    };
  } catch {
    return { value: sourceText || "(empty)", source: sourceText };
  }
}

function formatPrimitive(value: unknown): string {
  if (typeof value === "string") return JSON.stringify(value);
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  return String(value);
}
