// Adapted from pingdotgg/t3code MessagesTimeline.tsx virtualization and stable-row architecture (MIT).
import { LegendList, type LegendListRef } from "@legendapp/list/react";
import { createContext, memo, use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { DisplayStore } from "../lib/displayStore";
import { computeStableDisplayRows, deriveDisplayRows, type DisplayTimelineRow, type StableDisplayRowsState } from "../lib/displayRows";
import { MessageRow } from "./MessageRow";

interface TimelineSharedState {
  store: DisplayStore;
  onOpenPanel: (id: string) => void;
}

const TimelineRowCtx = createContext<TimelineSharedState>(null!);

export const DisplayTimeline = memo(function DisplayTimeline({ store, onOpenPanel }: { store: DisplayStore; onOpenPanel: (id: string) => void }) {
  const listRef = useRef<LegendListRef | null>(null);
  const rawRows = useMemo(() => deriveDisplayRows(store.messages), [store.messages]);
  const rows = useStableRows(rawRows);
  const shared = useMemo(() => ({ store, onOpenPanel }), [onOpenPanel, store]);

  useEffect(() => {
    if (!store.selectedId) return;
    const index = rows.findIndex((row) => row.id === store.selectedId);
    if (index >= 0) {
      listRef.current?.scrollToIndex?.({ index, animated: true });
    }
  }, [rows, store.selectedId]);

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
      <LegendList
        ref={listRef}
        data={rows}
        keyExtractor={(row) => row.id}
        renderItem={renderItem}
        style={{ height: "100%", minHeight: 0, overflowY: "auto" }}
        contentContainerStyle={{ minHeight: "100%" }}
        recycleItems
        ListHeaderComponent={<div className="timeline-pad" />}
        ListFooterComponent={<div className="timeline-pad" />}
      />
    </TimelineRowCtx>
  );
});

function TimelineRow({ row }: { row: DisplayTimelineRow }) {
  const { store, onOpenPanel } = use(TimelineRowCtx);
  const toggleExpanded = useCallback((id: string) => {
    store.toggleExpanded(id);
    window.requestAnimationFrame(() => {
      document.querySelector(`[data-message-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "nearest" });
    });
  }, [store]);
  if (row.kind === "empty") {
    return <div className="empty-state">No display messages yet.</div>;
  }
  return (
    <MessageRow
      api={store.api}
      message={row.message}
      expanded={store.expandedIds.has(row.id)}
      selected={store.selectedId === row.id}
      payload={store.payloadById.get(row.id)}
      onToggle={toggleExpanded}
      onOpenPanel={onOpenPanel}
    />
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
