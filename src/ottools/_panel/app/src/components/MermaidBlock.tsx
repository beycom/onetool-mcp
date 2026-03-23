import { useEffect, useId, useRef, useState } from "react";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  theme: "default",
  securityLevel: "loose",
});

interface MermaidBlockProps {
  code: string;
}

/**
 * Renders Mermaid DSL as an SVG diagram.
 * Falls back to showing the raw code if rendering fails.
 */
export function MermaidBlock({ code }: MermaidBlockProps) {
  const id = useId().replace(/:/g, "_");
  const elId = `mermaid_${id}`;
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function render() {
      try {
        const { svg } = await mermaid.render(elId, code.trim());
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      }
    }

    void render();
    return () => {
      cancelled = true;
    };
  }, [code, elId]);

  if (error) {
    return (
      <pre className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 p-2 rounded overflow-x-auto">
        {`Mermaid error: ${error}\n\n${code}`}
      </pre>
    );
  }

  return (
    <div
      ref={containerRef}
      className="mermaid-block overflow-x-auto my-2 flex justify-center"
    />
  );
}
