import { describe, expect, it } from "vitest";
import { sanitizeMermaidSvg } from "./MermaidViewer";

describe("sanitizeMermaidSvg", () => {
  it("removes executable SVG content before DOM insertion", () => {
    const unsafe = '<svg><script>alert(1)</script><a href="javascript:alert(1)"><rect onload="alert(2)" /></a></svg>';

    const safe = sanitizeMermaidSvg(unsafe);

    expect(safe).not.toContain("<script");
    expect(safe).not.toContain("javascript:");
    expect(safe).not.toContain("onload");
    expect(safe).not.toContain("href=");
  });
});
