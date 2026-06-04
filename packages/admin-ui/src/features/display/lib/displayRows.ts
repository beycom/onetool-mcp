// Adapted from pingdotgg/t3code MessagesTimeline.logic.ts stable row model (MIT).
import type { MessageMetadata } from "../types";

export type DisplayTimelineRow =
  | { kind: "empty"; id: "empty"; createdAt: string | null }
  | { kind: "message"; id: string; createdAt: string; message: MessageMetadata };

export interface StableDisplayRowsState {
  byId: Map<string, DisplayTimelineRow>;
  result: DisplayTimelineRow[];
}

export function deriveDisplayRows(messages: ReadonlyArray<MessageMetadata>): DisplayTimelineRow[] {
  if (messages.length === 0) {
    return [{ kind: "empty", id: "empty", createdAt: null }];
  }
  return messages.map((message) => ({
    kind: "message",
    id: message.id,
    createdAt: message.created_at,
    message,
  }));
}

export function computeStableDisplayRows(
  rows: DisplayTimelineRow[],
  previous: StableDisplayRowsState,
): StableDisplayRowsState {
  const next = new Map<string, DisplayTimelineRow>();
  let anyChanged = rows.length !== previous.byId.size;
  const result = rows.map((row, index) => {
    const prevRow = previous.byId.get(row.id);
    const nextRow = prevRow && isRowUnchanged(prevRow, row) ? prevRow : row;
    next.set(row.id, nextRow);
    if (!anyChanged && previous.result[index] !== nextRow) {
      anyChanged = true;
    }
    return nextRow;
  });
  return anyChanged ? { byId: next, result } : previous;
}

function isRowUnchanged(a: DisplayTimelineRow, b: DisplayTimelineRow): boolean {
  if (a.kind !== b.kind || a.id !== b.id) return false;
  if (a.kind === "empty") return b.kind === "empty";
  return b.kind === "message" && a.message === b.message;
}
