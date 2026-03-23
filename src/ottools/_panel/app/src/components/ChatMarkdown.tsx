import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeRaw from "rehype-raw";
import rehypeKatex from "rehype-katex";
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore -- katex CSS is resolved by Vite at bundle time
import "katex/dist/katex.min.css";
import { createHighlighter, type Highlighter } from "shiki";
import { LruCache } from "../lib/lruCache";
import { MermaidBlock } from "./MermaidBlock";
import type { Components } from "react-markdown";

// ---------------------------------------------------------------------------
// Theme helper — reads prefers-color-scheme
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Shiki highlighter (lazy singleton)
// ---------------------------------------------------------------------------

let highlighterPromise: Promise<Highlighter> | null = null;
const highlightCache = new LruCache<string, string>(128);

function getHighlighter(): Promise<Highlighter> {
  if (!highlighterPromise) {
    highlighterPromise = createHighlighter({
      themes: ["github-light", "github-dark"],
      langs: [
        "python",
        "javascript",
        "typescript",
        "tsx",
        "jsx",
        "json",
        "yaml",
        "bash",
        "sh",
        "sql",
        "rust",
        "go",
        "java",
        "c",
        "cpp",
        "markdown",
        "html",
        "css",
        "text",
      ],
    });
  }
  return highlighterPromise;
}

// ---------------------------------------------------------------------------
// ChatMarkdown component
// ---------------------------------------------------------------------------

interface ChatMarkdownProps {
  text: string;
}

export function ChatMarkdown({ text }: ChatMarkdownProps) {
  const theme = usePanelTheme();
  const shikiTheme = theme === "dark" ? "github-dark" : "github-light";

  const [, forceUpdate] = useState(0);

  // Eagerly load highlighter
  useEffect(() => {
    getHighlighter().then(() => forceUpdate((n) => n + 1));
  }, []);

  const components: Components = {
    // Intercept <pre><code> blocks for Shiki and Mermaid
    pre({ children, ...rest }) {
      // Extract the code element from children
      const codeEl =
        Array.isArray(children) ? children[0] : children;
      if (
        codeEl &&
        typeof codeEl === "object" &&
        "props" in codeEl
      ) {
        const props = codeEl.props as {
          className?: string;
          children?: string;
        };
        const className = props.className ?? "";
        const langMatch = /language-(\w+)/.exec(className);
        const lang = langMatch?.[1] ?? "text";
        const code =
          typeof props.children === "string"
            ? props.children
            : "";

        // Mermaid intercept
        if (lang === "mermaid") {
          return <MermaidBlock code={code} />;
        }

        // Shiki syntax highlighting
        const cacheKey = `${shikiTheme}:${lang}:${code}`;
        const cached = highlightCache.get(cacheKey);
        if (cached) {
          return (
            <div
              className="shiki"
              dangerouslySetInnerHTML={{ __html: cached }}
            />
          );
        }

        // Async: trigger highlight, re-render when done
        getHighlighter().then((hl) => {
          try {
            const html = hl.codeToHtml(code, {
              lang,
              theme: shikiTheme,
            });
            highlightCache.set(cacheKey, html);
            forceUpdate((n) => n + 1);
          } catch {
            // Unsupported language — fall through to plain pre
          }
        });

        // Render plain pre while highlight loads
        return (
          <pre
            {...rest}
            className="bg-gray-50 dark:bg-gray-900 rounded p-3 overflow-x-auto text-sm font-mono"
          >
            {children}
          </pre>
        );
      }

      return (
        <pre
          {...rest}
          className="bg-gray-50 dark:bg-gray-900 rounded p-3 overflow-x-auto text-sm font-mono"
        >
          {children}
        </pre>
      );
    },
  };

  return (
    <div className="panel-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeRaw, rehypeKatex]}
        components={components}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

