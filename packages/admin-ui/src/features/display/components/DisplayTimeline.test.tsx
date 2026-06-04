import { render, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DisplayTimeline } from "./DisplayTimeline";
import type { DisplayStore } from "../lib/displayStore";
import type { MessageMetadata } from "../types";

vi.mock("@legendapp/list/react", () => ({
  LegendList: ({ data, renderItem }: { data: unknown[]; renderItem: (input: { item: unknown }) => ReactNode }) => (
    <div>{data.map((item) => renderItem({ item }))}</div>
  ),
}));

describe("DisplayTimeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("prefetches a bounded recent payload window instead of every row", async () => {
    const store = fakeStore(Array.from({ length: 8 }, (_, index) => message(`msg-${index}`)));
    render(<DisplayTimeline store={store} onOpenPanel={vi.fn()} />);

    await waitFor(() => expect(store.loadPayload).toHaveBeenCalled());

    expect(store.loadPayload).toHaveBeenCalledTimes(3);
    expect(store.loadPayload).toHaveBeenCalledWith("msg-5");
    expect(store.loadPayload).toHaveBeenCalledWith("msg-6");
    expect(store.loadPayload).toHaveBeenCalledWith("msg-7");
  });
});

function fakeStore(messages: MessageMetadata[]): DisplayStore {
  return {
    api: {} as DisplayStore["api"],
    messages,
    selectedId: null,
    payloadById: new Map(),
    error: null,
    refresh: vi.fn(async () => undefined),
    loadPayload: vi.fn(),
    focusMessage: vi.fn(),
  };
}

function message(id: string): MessageMetadata {
  return {
    id,
    kind: "text",
    metadata: {},
    preview_lines: 1,
    created_at: "2026-06-04T00:00:00Z",
    updated_at: "2026-06-04T00:00:00Z",
    status: "ready",
    payload: {
      mode: "inline",
      size_bytes: 4,
      path: null,
      old_path: null,
      new_path: null,
      language: null,
      mime_type: null,
    },
  };
}
