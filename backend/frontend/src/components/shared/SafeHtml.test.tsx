import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";

import { SafeHtml } from "@/components/shared/SafeHtml";

describe("SafeHtml", () => {
  it("keeps ordinary lesson markup", () => {
    const { container } = render(
      <SafeHtml html="<h2>Title</h2><p>Body</p>" />,
    );

    expect(container.querySelector("h2")?.textContent).toBe("Title");
    expect(container.querySelector("p")?.textContent).toBe("Body");
  });

  it("removes scripts and inline event handlers", () => {
    const { container } = render(
      <SafeHtml html={'<p onclick="alert(1)">Safe</p><script>alert(2)</script>'} />,
    );

    const paragraph = container.querySelector("p");
    expect(paragraph?.textContent).toBe("Safe");
    expect(paragraph?.getAttribute("onclick")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
  });

  it("drops javascript: links", () => {
    const { container } = render(
      <SafeHtml html={'<a href="javascript:alert(1)">open</a>'} />,
    );

    const link = container.querySelector("a");
    expect(link?.getAttribute("href") ?? "").not.toContain("javascript:");
  });
});
