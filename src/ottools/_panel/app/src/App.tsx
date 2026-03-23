import { useState, useCallback } from "react";
import { MessagesTimeline } from "./components/MessagesTimeline";
import { usePanelWs } from "./hooks/usePanelWs";
import type { PanelMessage } from "./types";

export function App() {
  const [messages, setMessages] = useState<PanelMessage[]>([]);

  const onMessage = useCallback((msg: PanelMessage) => {
    setMessages((prev) => [...prev, msg]);
  }, []);

  const onClear = useCallback(() => {
    setMessages([]);
  }, []);

  usePanelWs({ onMessage, onClear });

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      <header className="flex-none px-4 py-2 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-400 dark:text-gray-600 tracking-wide uppercase">
          OneTool Panel
        </span>
        {messages.length > 0 && (
          <span className="text-xs text-gray-400">
            {messages.length} block{messages.length !== 1 ? "s" : ""}
          </span>
        )}
      </header>
      <main className="flex-1 overflow-hidden">
        <MessagesTimeline messages={messages} />
      </main>
    </div>
  );
}
