import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DisplayApi } from "../api/displayApi";
import type { DisplayEvent, MessageMetadata, PayloadView } from "../types";

const MAX_PAYLOAD_CACHE_ENTRIES = 100;

export interface DisplayStore {
  api: DisplayApi;
  messages: MessageMetadata[];
  selectedId: string | null;
  expandedIds: ReadonlySet<string>;
  payloadById: ReadonlyMap<string, PayloadView>;
  error: string | null;
  refresh: () => Promise<void>;
  loadPayload: (id: string) => void;
  toggleExpanded: (id: string) => void;
  focusMessage: (id: string) => void;
}

export function useDisplayStore(location: Location): DisplayStore {
  const api = useMemo(() => new DisplayApi(location), [location]);
  const [messages, setMessages] = useState<MessageMetadata[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<ReadonlySet<string>>(() => new Set());
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
      const list = await api.list();
      setMessages((current) => preserveMessageReferences(current, list.items));
      setExpandedIds((current) => mergeInitialExpansion(current, list.items));
      setPayloadById((current) => prunePayloadCache(current, list.items));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [api]);

  const focusMessage = useCallback((id: string) => {
    setSelectedId(id);
    setExpandedIds((current) => new Set(current).add(id));
  }, []);

  const toggleExpanded = useCallback(
    (id: string) => {
      setExpandedIds((current) => {
        const next = new Set(current);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
      loadPayload(id);
    },
    [loadPayload],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    for (const id of expandedIds) loadPayload(id);
  }, [expandedIds, loadPayload]);

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

  return { api, messages, selectedId, expandedIds, payloadById, error, refresh, loadPayload, toggleExpanded, focusMessage };
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
    left.title === right.title &&
    left.summary === right.summary &&
    left.source === right.source &&
    left.expand === right.expand &&
    left.preview_lines === right.preview_lines &&
    left.updated_at === right.updated_at &&
    left.status === right.status &&
    left.payload.size_bytes === right.payload.size_bytes &&
    left.payload.path === right.payload.path &&
    left.payload.language === right.payload.language
  );
}

function mergeInitialExpansion(
  current: ReadonlySet<string>,
  messages: ReadonlyArray<MessageMetadata>,
): ReadonlySet<string> {
  const next = new Set(current);
  for (const message of messages) {
    if (next.has(message.id)) continue;
    if (shouldStartExpanded(message)) next.add(message.id);
  }
  return next;
}

function shouldStartExpanded(message: MessageMetadata): boolean {
  if (message.expand === "expanded") return true;
  if (message.expand === "collapsed") return false;
  if (message.kind === "image") return true;
  const previewLines = message.preview_lines ?? 0;
  if (previewLines <= 1) return false;
  if (previewLines > 18) return false;
  return ["text", "markdown", "json", "yaml", "code"].includes(message.kind);
}
