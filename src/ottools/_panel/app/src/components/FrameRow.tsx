import { useEffect, useRef } from "react";
import type { FrameMessage } from "../types";

declare const __PANEL_PORT__: string;

interface FrameRowProps {
  msg: FrameMessage;
}

function getSandbox(type: string): string {
  if (type === "url") return "allow-scripts allow-same-origin allow-forms";
  return "allow-scripts";
}

function getSrc(msg: FrameMessage): string {
  const { source } = msg;
  switch (source.type) {
    case "inline": {
      const blob = new Blob([source.html], { type: "text/html" });
      return URL.createObjectURL(blob);
    }
    case "file":
      return `http://localhost:${__PANEL_PORT__}/file?path=${encodeURIComponent(source.path)}`;
    case "url":
      return source.url;
  }
}

/**
 * Sandboxed iframe renderer.
 * - inline/file: sandbox="allow-scripts" (no same-origin access to parent)
 * - url: sandbox="allow-scripts allow-same-origin allow-forms"
 * Listens for postMessage resize events from the iframe content.
 */
export function FrameRow({ msg }: FrameRowProps) {
  const { source, heightPx = 400 } = msg;
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const heightRef = useRef<number>(heightPx);
  const src = getSrc(msg);

  // Listen for resize messages from iframe content
  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (
        event.source !== iframeRef.current?.contentWindow ||
        typeof event.data !== "object" ||
        event.data === null
      )
        return;
      const d = event.data as { type?: string; height?: number };
      if (d.type === "resize" && typeof d.height === "number") {
        if (iframeRef.current) {
          iframeRef.current.style.height = `${d.height}px`;
          heightRef.current = d.height;
        }
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  return (
    <iframe
      ref={iframeRef}
      src={src}
      sandbox={getSandbox(source.type)}
      style={{ height: `${heightPx}px` }}
      className="w-full border-0 rounded overflow-hidden"
      title="panel frame"
    />
  );
}
