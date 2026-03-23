import type { ImageMessage } from "../types";

declare const __PANEL_PORT__: string;

interface ImageRowProps {
  msg: ImageMessage;
}

function resolveSrc(src: string): string {
  // data URIs and http/https URLs pass through directly
  if (src.startsWith("data:") || /^https?:\/\//.test(src)) return src;
  // Local absolute paths served via the file proxy
  return `http://localhost:${__PANEL_PORT__}/file?path=${encodeURIComponent(src)}`;
}

export function ImageRow({ msg }: ImageRowProps) {
  return (
    <img
      src={resolveSrc(msg.src)}
      alt={msg.alt ?? ""}
      className="max-w-full rounded"
    />
  );
}
