// Adapted from pingdotgg/t3code MessagesTimeline.tsx virtualization and stable-row architecture (MIT).
import { LegendList, type LegendListRef } from "@legendapp/list/react";
import { ArrowDownIcon } from "lucide-react";
import { createContext, memo, use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DisplayStore } from "../lib/displayStore";
import { computeStableDisplayRows, deriveDisplayRows, type DisplayTimelineRow, type StableDisplayRowsState } from "../lib/displayRows";
import { MessageRow } from "./MessageRow";

const INITIAL_PAYLOAD_PREFETCH_COUNT = 3;

interface TimelineSharedState {
  store: DisplayStore;
  onOpenPanel: (id: string) => void;
}

const TimelineRowCtx = createContext<TimelineSharedState>(null!);

export const DisplayTimeline = memo(function DisplayTimeline({ store, onOpenPanel }: { store: DisplayStore; onOpenPanel: (id: string) => void }) {
  const listRef = useRef<LegendListRef | null>(null);
  const [atBottom, setAtBottom] = useState(true);
  const [seenLastId, setSeenLastId] = useState<string | null>(null);
  const rawRows = useMemo(() => deriveDisplayRows(store.messages), [store.messages]);
  const rows = useStableRows(rawRows);
  const shared = useMemo(() => ({ store, onOpenPanel }), [onOpenPanel, store]);
  const lastMessageId = useMemo(() => {
    for (let index = rows.length - 1; index >= 0; index -= 1) {
      const row = rows[index];
      if (row.kind === "message") return row.id;
    }
    return null;
  }, [rows]);

  const scrollToBottom = useCallback((animated = true) => {
    if (rows.length === 0) return;
    void listRef.current?.scrollToIndex?.({ index: rows.length - 1, animated });
    setAtBottom(true);
    setSeenLastId(lastMessageId);
  }, [lastMessageId, rows.length]);

  useEffect(() => {
    if (!store.selectedId) return;
    const index = rows.findIndex((row) => row.id === store.selectedId);
    if (index >= 0) {
      void listRef.current?.scrollToIndex?.({ index, animated: true });
    }
  }, [rows, store.selectedId]);

  useEffect(() => {
    if (!lastMessageId) return;
    if (atBottom || seenLastId === null) {
      scrollToBottom(false);
      setSeenLastId(lastMessageId);
    }
  }, [atBottom, lastMessageId, scrollToBottom, seenLastId]);

  useEffect(() => {
    const recentMessages = rows.filter((row): row is Extract<DisplayTimelineRow, { kind: "message" }> => row.kind === "message").slice(-INITIAL_PAYLOAD_PREFETCH_COUNT);
    for (const row of recentMessages) {
      store.loadPayload(row.id);
    }
  }, [rows, store]);

  const onScroll = useCallback((event: { currentTarget?: EventTarget | null; nativeEvent?: { contentOffset?: { y?: number }; layoutMeasurement?: { height?: number }; contentSize?: { height?: number } } }) => {
    const native = event.nativeEvent;
    const distance = native?.contentSize?.height !== undefined
      ? native.contentSize.height - (native.contentOffset?.y ?? 0) - (native.layoutMeasurement?.height ?? 0)
      : domScrollDistance(event.currentTarget);
    setAtBottom(distance < 48);
  }, []);

  const renderItem = useCallback(
    ({ item }: { item: DisplayTimelineRow }) => (
      <div className="timeline-item">
        <TimelineRow row={item} />
      </div>
    ),
    [],
  );

  return (
    <TimelineRowCtx value={shared}>
      <div className="timeline-list-wrap">
        <LegendList
          ref={listRef}
          data={rows}
          keyExtractor={(row) => row.id}
          renderItem={renderItem}
          onScroll={onScroll}
          style={{ height: "100%", minHeight: 0, overflowY: "auto" }}
          contentContainerStyle={{ minHeight: "100%" }}
          recycleItems
          ListHeaderComponent={<div className="timeline-pad" />}
          ListFooterComponent={<div className="timeline-pad" />}
        />
        {!atBottom || seenLastId !== lastMessageId ? (
          <button type="button" className="scroll-bottom-button" onClick={() => scrollToBottom()} aria-label="Scroll to bottom" title="Scroll to bottom">
            <ArrowDownIcon size={16} />
            <span>Scroll to bottom</span>
          </button>
        ) : null}
      </div>
    </TimelineRowCtx>
  );
});

function domScrollDistance(target: EventTarget | null | undefined): number {
  if (!(target instanceof HTMLElement)) return 0;
  return target.scrollHeight - target.scrollTop - target.clientHeight;
}

function TimelineRow({ row }: { row: DisplayTimelineRow }) {
  const { store, onOpenPanel } = use(TimelineRowCtx);
  if (row.kind === "empty") {
    return <div className="empty-state">No display messages yet.</div>;
  }
  return <MessageTimelineRow store={store} onOpenPanel={onOpenPanel} row={row} />;
}

function MessageTimelineRow({ store, onOpenPanel, row }: { store: DisplayStore; onOpenPanel: (id: string) => void; row: Extract<DisplayTimelineRow, { kind: "message" }> }) {
  return (
    <div onMouseEnter={() => store.loadPayload(row.id)} onFocus={() => store.loadPayload(row.id)}>
      <MessageRow
        api={store.api}
        message={row.message}
        selected={store.selectedId === row.id}
        payload={store.payloadById.get(row.id)}
        onOpenPanel={onOpenPanel}
      />
    </div>
  );
}

function useStableRows(rows: DisplayTimelineRow[]): DisplayTimelineRow[] {
  const [state, setState] = useState<StableDisplayRowsState>(() => ({
    byId: new Map(),
    result: [],
  }));
  const next = useMemo(() => computeStableDisplayRows(rows, state), [rows, state]);
  useEffect(() => {
    if (next !== state) setState(next);
  }, [next, state]);
  return next.result;
}
