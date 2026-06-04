import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import {
  parseStructuredValue,
  SegmentedControl,
  STRUCTURED_MAX_DEPTH,
  STRUCTURED_MAX_SIBLINGS,
  STRUCTURED_SOURCE_LIMIT_BYTES,
  StructuredDataViewer,
} from "./StructuredDataViewer";

describe("StructuredDataViewer", () => {
  it("falls back to source for oversized input", () => {
    const source = "x".repeat(STRUCTURED_SOURCE_LIMIT_BYTES + 1);

    const parsed = parseStructuredValue("json", undefined, source);

    expect(parsed.truncated).toBe(true);
    expect(parsed.source).toBe(source);
  });

  it("bounds depth and sibling count", () => {
    let nested: Record<string, unknown> = { value: "end" };
    for (let index = 0; index < STRUCTURED_MAX_DEPTH + 2; index += 1) {
      nested = { child: nested };
    }
    const wide = Object.fromEntries(Array.from({ length: STRUCTURED_MAX_SIBLINGS + 20 }, (_, index) => [`key-${index}`, index]));

    const nestedResult = parseStructuredValue("json", nested, JSON.stringify(nested));
    const wideResult = parseStructuredValue("json", wide, JSON.stringify(wide));

    expect(JSON.stringify(nestedResult.value)).toContain("max depth reached");
    expect(Object.keys(wideResult.value as Record<string, unknown>)).toHaveLength(STRUCTURED_MAX_SIBLINGS);
  });

  it("does not render descendants for closed nodes", async () => {
    const user = userEvent.setup();
    render(<StructuredDataViewer kind="json" text='{"child":{"secret":"hidden"}}' content={{ child: { secret: "hidden" } }} />);

    await user.click(screen.getByRole("button", { name: /root/i }));

    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });

  it("supports keyboard navigation in segmented controls", async () => {
    const user = userEvent.setup();
    let selected = "tree";
    const { rerender } = render(
      <SegmentedControl value={selected} options={["tree", "source"]} onChange={(value) => { selected = value; }} />,
    );

    await user.tab();
    await user.keyboard("{ArrowRight}");
    rerender(<SegmentedControl value={selected} options={["tree", "source"]} onChange={(value) => { selected = value; }} />);

    expect(screen.getByRole("tab", { selected: true })).toHaveTextContent("source");
  });
});
