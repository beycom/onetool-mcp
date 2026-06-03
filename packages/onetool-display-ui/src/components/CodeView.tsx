import { File } from "@pierre/diffs/react";
import { memo, useMemo } from "react";
import { useDisplaySettings } from "../lib/displaySettings";
import { resolveDiffThemeName } from "../lib/diffRendering";

export const CodeView = memo(function CodeView({
  text,
  language,
  name = "artifact",
  showHeader = true,
}: {
  text: string;
  language?: string | null;
  name?: string | null;
  showHeader?: boolean;
}) {
  const { codeTheme, wrapDiff } = useDisplaySettings();
  const file = useMemo(
    () => ({
      name: name || extensionName(language),
      contents: text,
      lang: normalizeDiffLanguage(language),
      cacheKey: `${name ?? "artifact"}:${language ?? "text"}:${text.length}`,
    }),
    [language, name, text],
  );
  return (
    <div className="code-view">
      <File file={file} options={{ theme: resolveDiffThemeName(codeTheme), overflow: wrapDiff ? "wrap" : "scroll", disableFileHeader: !showHeader }} />
    </div>
  );
});

function normalizeDiffLanguage(language: string | null | undefined) {
  const normalized = language?.trim().toLowerCase();
  if (!normalized || normalized === "text") return undefined;
  return normalized === "python" ? "py" : normalized;
}

function extensionName(language: string | null | undefined): string {
  const normalized = language?.trim().toLowerCase();
  return normalized ? `artifact.${normalized}` : "artifact.txt";
}
