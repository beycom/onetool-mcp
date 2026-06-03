// Renderer structure adapted from pingdotgg/t3code ChatMarkdown.tsx (MIT).
import { CheckIcon, CopyIcon } from "lucide-react";
import { memo, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getSharedHighlighter, type DiffsHighlighter, type SupportedLanguages } from "@pierre/diffs";
import { fnv1a32, resolveDiffThemeName, type DiffThemeName } from "../lib/diffRendering";
import { useDisplaySettings } from "../lib/displaySettings";
import { LRUCache } from "../lib/lruCache";

const CODE_FENCE_LANGUAGE_REGEX = /(?:^|\s)language-([^\s]+)/;
const MAX_HIGHLIGHTER_PROMISES = 64;
const highlightedCodeCache = new LRUCache<string>(500, 50 * 1024 * 1024);
const highlighterPromiseCache = new Map<string, Promise<DiffsHighlighter>>();

export const MarkdownRenderer = memo(function MarkdownRenderer({ text, copyCode = true }: { text: string; copyCode?: boolean }) {
  const { codeTheme } = useDisplaySettings();
  const themeName = resolveDiffThemeName(codeTheme);
  return (
    <div className="markdown-viewer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          pre({ children }) {
            const code = nodeToPlainText(children);
            const className = extractCodeClassName(children);
            return (
              <MarkdownCodeBlock code={code} copyCode={copyCode}>
                <Suspense fallback={<pre className="code-block"><code>{code}</code></pre>}>
                  <HighlightedCodeBlock code={code} className={className} themeName={themeName} />
                </Suspense>
              </MarkdownCodeBlock>
            );
          },
          a({ href, children }) {
            return (
              <a href={href} rel="noreferrer" target="_blank">
                {children}
              </a>
            );
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
});

function MarkdownCodeBlock({ code, copyCode, children }: { code: string; copyCode: boolean; children: ReactNode }) {
  const [copied, setCopied] = useState(false);
  const copiedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const copy = useCallback(() => {
    void navigator.clipboard?.writeText(code).then(() => {
      if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current);
      setCopied(true);
      copiedTimerRef.current = setTimeout(() => setCopied(false), 1200);
    });
  }, [code]);
  useEffect(
    () => () => {
      if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current);
    },
    [],
  );
  return (
    <div className="code-shell">
      {copyCode ? (
        <button type="button" className="icon-button code-copy" onClick={copy} aria-label={copied ? "Copied" : "Copy code"}>
          {copied ? <CheckIcon size={14} /> : <CopyIcon size={14} />}
        </button>
      ) : null}
      {children}
    </div>
  );
}

function HighlightedCodeBlock({ code, className, themeName }: { code: string; className?: string; themeName: DiffThemeName }) {
  const language = extractFenceLanguage(className);
  const cacheKey = `${fnv1a32(code).toString(36)}:${code.length}:${language}:${themeName}`;
  const cached = highlightedCodeCache.get(cacheKey);
  if (cached) return <div className="shiki-block" dangerouslySetInnerHTML={{ __html: cached }} />;
  return <UncachedHighlightedCodeBlock code={code} language={language} themeName={themeName} cacheKey={cacheKey} />;
}

function UncachedHighlightedCodeBlock({ code, language, themeName, cacheKey }: { code: string; language: string; themeName: DiffThemeName; cacheKey: string }) {
  const highlighter = useHighlighter(language);
  const html = useMemo(() => {
    try {
      return highlighter.codeToHtml(code, { lang: language, theme: themeName });
    } catch {
      return highlighter.codeToHtml(code, { lang: "text", theme: themeName });
    }
  }, [code, highlighter, language, themeName]);
  useEffect(() => {
    highlightedCodeCache.set(cacheKey, html, Math.max(html.length * 2, code.length * 3));
  }, [cacheKey, code, html]);
  return <div className="shiki-block" dangerouslySetInnerHTML={{ __html: html }} />;
}

function useHighlighter(language: string): DiffsHighlighter {
  const promise = getHighlighterPromise(language);
  // React 19's `use` is intentionally avoided here to keep the component
  // compatible with esbuild's default JSX transform; throwing the promise lets
  // Suspense handle the async highlighter boundary.
  const record = promise as Promise<DiffsHighlighter> & { value?: DiffsHighlighter; reason?: unknown };
  if (record.value) return record.value;
  if (record.reason) throw record.reason;
  void promise.then(
    (value) => {
      record.value = value;
    },
    (reason) => {
      record.reason = reason;
    },
  );
  throw promise;
}

function getHighlighterPromise(language: string): Promise<DiffsHighlighter> {
  const cached = highlighterPromiseCache.get(language);
  if (cached) return cached;
  const promise = getSharedHighlighter({
    themes: [resolveDiffThemeName("dark"), resolveDiffThemeName("light")],
    langs: [language as SupportedLanguages],
    preferredHighlighter: "shiki-js",
  }).catch((err) => {
    highlighterPromiseCache.delete(language);
    if (language === "text") throw err;
    return getHighlighterPromise("text");
  });
  setHighlighterPromise(language, promise);
  return promise;
}

function setHighlighterPromise(language: string, promise: Promise<DiffsHighlighter>): void {
  while (highlighterPromiseCache.size >= MAX_HIGHLIGHTER_PROMISES) {
    const oldest = highlighterPromiseCache.keys().next().value;
    if (oldest === undefined) break;
    highlighterPromiseCache.delete(oldest);
  }
  highlighterPromiseCache.set(language, promise);
}

function extractFenceLanguage(className: string | undefined): string {
  const raw = className?.match(CODE_FENCE_LANGUAGE_REGEX)?.[1] ?? "text";
  return raw === "gitignore" ? "ini" : raw;
}

function extractCodeClassName(node: ReactNode): string | undefined {
  if (Array.isArray(node)) return node.map(extractCodeClassName).find(Boolean);
  if (typeof node === "object" && node !== null && "props" in node) {
    const props = (node as { props?: { className?: string; children?: ReactNode } }).props;
    return props?.className ?? extractCodeClassName(props?.children);
  }
  return undefined;
}

function nodeToPlainText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(nodeToPlainText).join("");
  if (typeof node === "object" && node !== null && "props" in node) {
    return nodeToPlainText((node as { props?: { children?: ReactNode } }).props?.children);
  }
  return "";
}
