import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore -- xterm CSS is resolved by Vite at bundle time
import "@xterm/xterm/css/xterm.css";
import type { TerminalMessage } from "../types";

interface TerminalRowProps {
  msg: TerminalMessage;
}

/**
 * xterm.js terminal renderer.
 * - ANSI escape codes preserved (colors, bold, etc.)
 * - Read-only (disableStdin: true)
 * - FitAddon for responsive width
 */
export function TerminalRow({ msg }: TerminalRowProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const term = new Terminal({
      convertEol: true,
      disableStdin: true,
      scrollback: 10000,
      fontSize: 13,
      fontFamily: "monospace",
      theme: {
        background: "#1e1e1e",
        foreground: "#d4d4d4",
      },
    });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(el);
    fitAddon.fit();
    term.write(msg.text);
    termRef.current = term;

    const observer = new ResizeObserver(() => fitAddon.fit());
    observer.observe(el);

    return () => {
      observer.disconnect();
      term.dispose();
      termRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      {msg.label && (
        <div className="text-xs font-semibold text-gray-500 dark:text-gray-400 mb-1">
          {msg.label}
        </div>
      )}
      <div
        ref={containerRef}
        style={{ minHeight: "200px" }}
        className="rounded overflow-hidden"
      />
    </div>
  );
}
