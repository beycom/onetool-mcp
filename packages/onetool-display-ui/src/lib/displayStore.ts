import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { DisplayApi } from "../api/displayApi";
import type { DisplayEvent, MessageMetadata, PayloadView } from "../types";

const MAX_PAYLOAD_CACHE_ENTRIES = 100;
const DISPLAY_MESSAGES_LIMIT = 300;
const PAYLOAD_STALE_MS = 5 * 60 * 1000;
const PAYLOAD_GC_MS = 10 * 60 * 1000;

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
  const queryClient = useQueryClient();
  const api = useMemo(() => new DisplayApi(location), [location]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [payloadVersion, setPayloadVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const pendingPayloadIdsRef = useRef<Set<string>>(new Set());
  const messageQuery = useQuery({
    queryKey: displayMessagesKey(api.instanceId),
    queryFn: () => api.list(DISPLAY_MESSAGES_LIMIT, { tail: true }),
    refetchOnWindowFocus: false,
  });
  const messages = useMemo(
    () => preserveMessageReferences([], messageQuery.data?.items ?? []),
    [messageQuery.data?.items],
  );
  const payloadById = useMemo(
    () => {
      void payloadVersion;
      return collectCachedPayloads(queryClient, api.instanceId, messages);
    },
    [api.instanceId, messages, payloadVersion, queryClient],
  );

  const loadPayload = useCallback(
    (id: string) => {
      if (queryClient.getQueryData(payloadKey(api.instanceId, id)) || pendingPayloadIdsRef.current.has(id)) return;
      pendingPayloadIdsRef.current.add(id);
      void queryClient
        .fetchQuery({
          queryKey: payloadKey(api.instanceId, id),
          queryFn: () => api.payload(id),
          staleTime: PAYLOAD_STALE_MS,
          gcTime: PAYLOAD_GC_MS,
        })
        .then(() => {
          prunePayloadQueries(queryClient, api.instanceId, messages);
          setPayloadVersion((value) => value + 1);
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : String(err));
        })
        .finally(() => {
          pendingPayloadIdsRef.current.delete(id);
        });
    },
    [api, messages, queryClient],
  );

  const refresh = useCallback(async () => {
    try {
      await queryClient.invalidateQueries({ queryKey: displayMessagesKey(api.instanceId) });
      prunePayloadQueries(queryClient, api.instanceId, messages);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [api.instanceId, messages, queryClient]);

  const focusMessage = useCallback((id: string) => {
    setSelectedId(id);
    loadPayload(id);
  }, [loadPayload]);

  useEffect(() => {
    if (messageQuery.error) {
      setError(messageQuery.error instanceof Error ? messageQuery.error.message : String(messageQuery.error));
    } else if (messageQuery.data) {
      setError(null);
    }
  }, [messageQuery.data, messageQuery.error]);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const events = await api.events();
        applyEvents(events, { refresh, focusMessage });
      } finally {
        if (!cancelled) window.setTimeout(() => void poll(), 900);
      }
    };
    void poll();
    return () => {
      cancelled = true;
    };
  }, [api, focusMessage, refresh]);

  return { api, messages, selectedId, payloadById, error, refresh, loadPayload, focusMessage };
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

export function displayMessagesKey(instanceId: string): readonly ["display", string, "messages"] {
  return ["display", instanceId, "messages"] as const;
}

export function payloadKey(instanceId: string, messageId: string): readonly ["display", string, "payload", string] {
  return ["display", instanceId, "payload", messageId] as const;
}

function collectCachedPayloads(
  queryClient: ReturnType<typeof useQueryClient>,
  instanceId: string,
  messages: ReadonlyArray<MessageMetadata>,
): ReadonlyMap<string, PayloadView> {
  const next = new Map<string, PayloadView>();
  for (const message of messages) {
    const payload = queryClient.getQueryData<PayloadView>(payloadKey(instanceId, message.id));
    if (payload) next.set(message.id, payload);
  }
  return next;
}

function prunePayloadQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  instanceId: string,
  messages: ReadonlyArray<MessageMetadata>,
): void {
  const liveIds = new Set(messages.map((message) => message.id));
  const cached = queryClient
    .getQueryCache()
    .findAll({ queryKey: ["display", instanceId, "payload"] })
    .filter((query) => typeof query.queryKey[3] === "string");
  for (const query of cached) {
    const id = query.queryKey[3] as string;
    if (!liveIds.has(id)) {
      queryClient.removeQueries({ queryKey: payloadKey(instanceId, id), exact: true });
    }
  }
  const retained = cached.filter((query) => liveIds.has(query.queryKey[3] as string));
  for (const query of retained.slice(0, Math.max(0, retained.length - MAX_PAYLOAD_CACHE_ENTRIES))) {
    queryClient.removeQueries({
      queryKey: payloadKey(instanceId, query.queryKey[3] as string),
      exact: true,
    });
  }
}
