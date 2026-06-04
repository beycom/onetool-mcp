import { MaximizeIcon, MinusIcon, PlusIcon, RotateCcwIcon } from "lucide-react";
import { memo, useEffect, useId, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import DOMPurify from "dompurify";
import { CodeView } from "./CodeView";
import { SegmentedControl } from "./StructuredDataViewer";

export const MermaidViewer = memo(function MermaidViewer({ source }: { source: string }) {
  const elementId = useId().replace(/:/g, "");
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"render" | "source">("render");
  const [scale, setScale] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const activePanCleanupRef = useRef<(() => void) | null>(null);
  const diagramSource = useMemo(() => source.trim(), [source]);
  useEffect(() => () => {
    activePanCleanupRef.current?.();
    activePanCleanupRef.current = null;
  }, []);

  useEffect(() => {
    let cancelled = false;
    const render = async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: resolveMermaidTheme() });
        const { svg } = await mermaid.render(`onetool-display-${elementId}`, diagramSource);
        if (cancelled || !containerRef.current) return;
        containerRef.current.innerHTML = sanitizeMermaidSvg(svg);
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

  const startPan = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (view !== "render") return;
    activePanCleanupRef.current?.();
    event.currentTarget.setPointerCapture(event.pointerId);
    const start = { x: event.clientX, y: event.clientY, offset };
    const onMove = (moveEvent: PointerEvent) => {
      setOffset({ x: start.offset.x + moveEvent.clientX - start.x, y: start.offset.y + moveEvent.clientY - start.y });
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      activePanCleanupRef.current = null;
    };
    activePanCleanupRef.current = onUp;
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp, { once: true });
  };

  return (
    <div className="mermaid-preview">
      <div className="viewer-toolbar">
        <SegmentedControl value={view} options={["render", "source"]} onChange={setView} />
        <button type="button" className="icon-button row-action" onClick={() => setScale((value) => Math.max(0.25, value - 0.15))} aria-label="Zoom out" title="Zoom out">
          <MinusIcon size={14} />
        </button>
        <button type="button" className="icon-button row-action" onClick={() => setScale((value) => Math.min(3, value + 0.15))} aria-label="Zoom in" title="Zoom in">
          <PlusIcon size={14} />
        </button>
        <button type="button" className="icon-button row-action" onClick={() => { setScale(1); setOffset({ x: 0, y: 0 }); }} aria-label="Reset view" title="Reset">
          <RotateCcwIcon size={14} />
        </button>
        <button type="button" className="icon-button row-action" onClick={() => { setScale(0.85); setOffset({ x: 0, y: 0 }); }} aria-label="Fit diagram" title="Fit">
          <MaximizeIcon size={14} />
        </button>
      </div>
      {view === "source" || error ? <CodeView text={diagramSource} language="mermaid" name="diagram.mmd" /> : null}
      {error ? <p className="error-text">{error}</p> : null}
      <div className={view === "render" && !error ? "mermaid-canvas" : "mermaid-canvas hidden"} onPointerDown={startPan}>
        <div ref={containerRef} className="mermaid-surface" style={{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})` }} />
      </div>
    </div>
  );
});

export function sanitizeMermaidSvg(svg: string): string {
  return DOMPurify.sanitize(svg, {
    USE_PROFILES: { svg: true, svgFilters: true },
    FORBID_ATTR: ["onload", "onclick", "onerror", "href", "xlink:href"],
    FORBID_TAGS: ["script", "foreignObject", "iframe", "object", "embed"],
  });
}

function resolveMermaidTheme(): "default" | "dark" {
  const theme = document.documentElement.dataset.theme;
  if (theme === "light") return "default";
  if (theme === "dark") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "default" : "dark";
}
