import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DisplayApi } from "../api/displayApi";
import type { DisplayEvent, MessageMetadata, PayloadView } from "../types";

const MAX_PAYLOAD_CACHE_ENTRIES = 100;

export interface DisplayStore {
  api: DisplayApi;
  messages: MessageMetadata[];
  selectedId: string | null;
  payloadById: ReadonlyMap<string, PayloadView>;
  error: string | null;
  refresh: () => Promise<void>;
  loadPayload: (id: string) => void;
  focusMessage: (id: string) => void;
}

export function useDisplayStore(location: Location): DisplayStore {
  const api = useMemo(() => new DisplayApi(location), [location]);
  const [messages, setMessages] = useState<MessageMetadata[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [payloadById, setPayloadById] = useState<ReadonlyMap<string, PayloadView>>(() => new Map());
  const [error, setError] = useState<string | null>(null);
  const payloadByIdRef = useRef(payloadById);
  const pendingPayloadIdsRef = useRef<Set<string>>(new Set());
  payloadByIdRef.current = payloadById;

  const loadPayload = useCallback(
    (id: string) => {
      if (payloadByIdRef.current.has(id) || pendingPayloadIdsRef.current.has(id)) return;
      pendingPayloadIdsRef.current.add(id);
      void api
        .payload(id)
        .then((payload) => {
          setPayloadById((current) => withPayloadCacheLimit(new Map(current).set(id, payload)));
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : String(err));
        })
        .finally(() => {
          pendingPayloadIdsRef.current.delete(id);
        });
    },
    [api],
  );

  const refresh = useCallback(async () => {
    try {
      const list = await api.list(300, { tail: true });
      setMessages((current) => preserveMessageReferences(current, list.items));
      setPayloadById((current) => prunePayloadCache(current, list.items));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [api]);

  const focusMessage = useCallback((id: string) => {
    setSelectedId(id);
    loadPayload(id);
  }, [loadPayload]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const events = await api.events();
        applyEvents(events, { refresh, focusMessage });
      } finally {
        if (!cancelled) window.setTimeout(poll, 900);
      }
    };
    void poll();
    return () => {
      cancelled = true;
    };
  }, [api, focusMessage, refresh]);

  return { api, messages, selectedId, payloadById, error, refresh, loadPayload, focusMessage };
}

function withPayloadCacheLimit(payloads: Map<string, PayloadView>): Map<string, PayloadView> {
  while (payloads.size > MAX_PAYLOAD_CACHE_ENTRIES) {
    const oldest = payloads.keys().next().value;
    if (oldest === undefined) break;
    payloads.delete(oldest);
  }
  return payloads;
}

function prunePayloadCache(
  current: ReadonlyMap<string, PayloadView>,
  messages: ReadonlyArray<MessageMetadata>,
): ReadonlyMap<string, PayloadView> {
  const liveIds = new Set(messages.map((message) => message.id));
  const next = new Map<string, PayloadView>();
  for (const [id, payload] of current) {
    if (liveIds.has(id)) next.set(id, payload);
  }
  return withPayloadCacheLimit(next);
}

function applyEvents(
  events: DisplayEvent[],
  handlers: { refresh: () => Promise<void>; focusMessage: (id: string) => void },
) {
  let sawMessage = false;
  for (const event of events) {
    if (event.type === "message") sawMessage = true;
    if (event.type === "focus") handlers.focusMessage(event.id);
  }
  if (sawMessage) void handlers.refresh();
}

function preserveMessageReferences(
  current: ReadonlyArray<MessageMetadata>,
  next: ReadonlyArray<MessageMetadata>,
): MessageMetadata[] {
  const byId = new Map(current.map((message) => [message.id, message]));
  return next.map((message) => {
    const previous = byId.get(message.id);
    return previous && shallowMessageEqual(previous, message) ? previous : message;
  });
}

function shallowMessageEqual(left: MessageMetadata, right: MessageMetadata): boolean {
  return (
    left.id === right.id &&
    left.kind === right.kind &&
    shallowRecordEqual(left.metadata, right.metadata) &&
    left.preview_lines === right.preview_lines &&
    left.updated_at === right.updated_at &&
    left.status === right.status &&
    left.payload.size_bytes === right.payload.size_bytes &&
    left.payload.path === right.payload.path &&
    left.payload.old_path === right.payload.old_path &&
    left.payload.new_path === right.payload.new_path &&
    left.payload.language === right.payload.language
  );
}

function shallowRecordEqual(left: Record<string, string>, right: Record<string, string>): boolean {
  const leftEntries = Object.entries(left);
  if (leftEntries.length !== Object.keys(right).length) return false;
  return leftEntries.every(([key, value]) => right[key] === value);
}
