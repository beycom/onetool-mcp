import { useEffect, useState } from "react";
import { createHighlighter } from "shiki";
import { LruCache } from "../lib/lruCache";
import type { DiffMessage } from "../types";

let highlighterPromise: Promise<Awaited<ReturnType<typeof createHighlighter>>> | null =
  null;
const cache = new LruCache<string, string>(64);

function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: ["github-light", "github-dark"],
      langs: ["text", "python", "typescript", "javascript", "go", "rust", "json", "yaml", "bash", "sql"],
    });
  }
  return highlighterPromise;
}

function usePanelTheme(): "dark" | "light" {
  const [theme, setTheme] = useState<"dark" | "light">(() =>
    window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
  );
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) =>
      setTheme(e.matches ? "dark" : "light");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return theme;
}

interface DiffRowProps {
  msg: DiffMessage;
}

function computeUnifiedDiff(before: string, after: string): string {
  const beforeLines = before.split("\n");
  const afterLines = after.split("\n");
  const lines: string[] = [];

  // Simple unified diff (no hunks, just mark all lines)
  const removed = beforeLines.filter((l) => !afterLines.includes(l));
  const added = afterLines.filter((l) => !beforeLines.includes(l));

  for (const l of beforeLines) {
    if (removed.includes(l)) {
      lines.push(`- ${l}`);
    } else {
      lines.push(`  ${l}`);
    }
  }
  for (const l of afterLines) {
    if (added.includes(l)) {
      lines.push(`+ ${l}`);
    }
  }

  return lines.join("\n");
}

export function DiffRow({ msg }: DiffRowProps) {
  const { before, after, lang = "text", mode = "split" } = msg;
  const theme = usePanelTheme();
  const shikiTheme = theme === "dark" ? "github-dark" : "github-light";
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    getHighlighter().then(() => forceUpdate((n) => n + 1));
  }, []);

  function highlight(code: string): string {
    const key = `${shikiTheme}:${lang}:${code}`;
    const cached = cache.get(key);
    if (cached) return cached;
    // Return raw code until highlighter ready
    getHighlighter().then((hl) => {
      try {
        const html = hl.codeToHtml(code, { lang, theme: shikiTheme });
        cache.set(key, html);
        forceUpdate((n) => n + 1);
      } catch {
        // unsupported lang
      }
    });
    return `<pre class="shiki"><code>${code.replace(/</g, "&lt;")}</code></pre>`;
  }

  if (mode === "unified") {
    const unified = computeUnifiedDiff(before, after);
    return (
      <div>
        <div className="text-xs font-semibold text-gray-500 mb-1">
          diff ({lang})
        </div>
        <div
          className="shiki text-xs"
          dangerouslySetInnerHTML={{ __html: highlight(unified) }}
        />
      </div>
    );
  }

  // Split mode (side by side)
  return (
    <div>
      <div className="text-xs font-semibold text-gray-500 mb-1">
        diff ({lang})
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <div className="text-xs text-red-500 font-semibold mb-1">before</div>
          <div
            className="shiki text-xs"
            dangerouslySetInnerHTML={{ __html: highlight(before) }}
          />
        </div>
        <div>
          <div className="text-xs text-green-600 font-semibold mb-1">after</div>
          <div
            className="shiki text-xs"
            dangerouslySetInnerHTML={{ __html: highlight(after) }}
          />
        </div>
      </div>
    </div>
  );
}
