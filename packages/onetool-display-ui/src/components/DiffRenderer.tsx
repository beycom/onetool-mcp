// Diff rendering pattern adapted from t3code DiffPanel and diffRendering helpers (MIT).
import { FileDiff } from "@pierre/diffs/react";
import { memo, useMemo } from "react";
import { useDisplaySettings } from "../lib/displaySettings";
import { getRenderablePatch, resolveDiffThemeName, resolveFileDiffPath } from "../lib/diffRendering";

export const DiffRenderer = memo(function DiffRenderer({ patch }: { patch: string }) {
  const { wrapDiff } = useDisplaySettings();
  const renderable = useMemo(() => getRenderablePatch(patch), [patch]);
  if (!renderable) return <p className="muted">No diff content.</p>;
  if (renderable.kind === "raw") {
    return (
      <div>
        <p className="muted">{renderable.reason}</p>
        <pre className="raw-block">{renderable.text}</pre>
      </div>
    );
  }
  return (
    <div className="diff-stack">
      {renderable.files.map((file) => (
        <div key={file.cacheKey ?? `${file.prevName}:${file.name}`} className="diff-file" data-diff-file-path={resolveFileDiffPath(file)}>
          <FileDiff fileDiff={file} options={{ theme: resolveDiffThemeName("dark"), overflow: wrapDiff ? "wrap" : "scroll" }} />
        </div>
      ))}
    </div>
  );
});
