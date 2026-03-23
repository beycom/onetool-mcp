import { useEffect, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { PanelMessage } from "../types";
import { MarkdownRow } from "./MarkdownRow";
import { FrameRow } from "./FrameRow";
import { ImageRow } from "./ImageRow";
import { JsonRow } from "./JsonRow";
import { YamlRow } from "./YamlRow";
import { TableRow } from "./TableRow";
import { DiffRow } from "./DiffRow";
import { TerminalRow } from "./TerminalRow";

interface MessagesTimelineProps {
  messages: PanelMessage[];
}

function renderRow(msg: PanelMessage): React.ReactNode {
  switch (msg.kind) {
    case "markdown":
      return <MarkdownRow msg={msg} />;
    case "frame":
      return <FrameRow msg={msg} />;
    case "image":
      return <ImageRow msg={msg} />;
    case "json":
      return <JsonRow msg={msg} />;
    case "yaml":
      return <YamlRow msg={msg} />;
    case "table":
      return <TableRow msg={msg} />;
    case "diff":
      return <DiffRow msg={msg} />;
    case "terminal":
      return <TerminalRow msg={msg} />;
    default:
      return null;
  }
}

/**
 * Virtualised scrolling timeline. Uses dynamic measurement so rows of any
 * height (terminal, diff, markdown) position correctly.
 */
export function MessagesTimeline({ messages }: MessagesTimelineProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);

  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    // Generous initial estimate — virtualizer replaces this with measured values
    estimateSize: () => 300,
    overscan: 3,
  });

  // Track whether the user is pinned to the bottom
  useEffect(() => {
    const el = parentRef.current;
    if (!el) return;
    const onScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = el;
      pinnedRef.current = scrollHeight - scrollTop - clientHeight < 80;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Auto-scroll to bottom when new messages arrive (only if pinned)
  useEffect(() => {
    if (pinnedRef.current && messages.length > 0) {
      virtualizer.scrollToIndex(messages.length - 1, { align: "end" });
    }
  }, [messages.length, virtualizer]);

  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 dark:text-gray-600 text-sm select-none">
        Panel ready — waiting for content
      </div>
    );
  }

  const items = virtualizer.getVirtualItems();

  return (
    <div ref={parentRef} className="h-full overflow-y-auto">
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {items.map((item) => (
          <div
            key={messages[item.index].id}
            data-index={item.index}
            ref={virtualizer.measureElement}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              transform: `translateY(${item.start}px)`,
            }}
          >
            <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800">
              {renderRow(messages[item.index])}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
