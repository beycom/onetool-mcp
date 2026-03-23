import { useEffect, useRef } from "react";
import type { PanelMessage, ClearMessage } from "../types";

declare const __PANEL_PORT__: string;

interface UsePanelWsOptions {
  onMessage: (msg: PanelMessage) => void;
  onClear: () => void;
}

/**
 * WebSocket hook that connects to the panel server and dispatches messages.
 * Reconnects automatically after 1 second on error or unexpected close.
 */
export function usePanelWs({ onMessage, onClear }: UsePanelWsOptions): void {
  const onMessageRef = useRef(onMessage);
  const onClearRef = useRef(onClear);
  onMessageRef.current = onMessage;
  onClearRef.current = onClear;

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;

    function connect(): void {
      const url = `ws://localhost:${__PANEL_PORT__}/ws`;
      ws = new WebSocket(url);

      ws.onmessage = (event: MessageEvent<string>) => {
        let data: unknown;
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }
        if (
          typeof data !== "object" ||
          data === null ||
          !("kind" in data) ||
          typeof (data as { kind: unknown }).kind !== "string"
        ) {
          return;
        }
        const msg = data as { kind: string };
        if (msg.kind === "clear") {
          onClearRef.current();
        } else {
          onMessageRef.current(data as PanelMessage);
        }
      };

      ws.onerror = () => scheduleReconnect();
      ws.onclose = () => scheduleReconnect();
    }

    function scheduleReconnect(): void {
      if (stopped) return;
      reconnectTimer = setTimeout(() => {
        if (!stopped) connect();
      }, 1000);
    }

    connect();

    return () => {
      stopped = true;
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
}

// Re-export for type consumers
export type { ClearMessage };
