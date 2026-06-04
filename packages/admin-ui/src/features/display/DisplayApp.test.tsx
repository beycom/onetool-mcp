import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DisplayAppShell } from "./DisplayApp";
import type { DisplayStore } from "./lib/displayStore";

describe("DisplayAppShell", () => {
  it("updates panel width through keyboard-accessible resizer", async () => {
    const user = userEvent.setup();
    render(<DisplayAppShell store={fakeStore()} label="test-instance" />);

    const resizer = screen.getByRole("separator", { name: "Resize message inspector" });
    resizer.focus();
    await user.keyboard("{ArrowLeft}");

    expect(resizer).toHaveAttribute("aria-valuenow", "576");
  });
});

function fakeStore(): DisplayStore {
  return {
    api: {} as DisplayStore["api"],
    messages: [],
    selectedId: null,
    payloadById: new Map(),
    error: null,
    refresh: vi.fn(async () => undefined),
    loadPayload: vi.fn(),
    focusMessage: vi.fn(),
  };
}
