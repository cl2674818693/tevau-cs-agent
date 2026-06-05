/** F-P1-2: 验证 safeMarkdownProps 拦截危险协议 + 危险标签。 */
import { render } from "@testing-library/react";
import ReactMarkdown from "react-markdown";
import { describe, expect, it } from "vitest";

import { safeMarkdownProps, safeMarkdownUrl } from "@/lib/markdown-safe";

describe("safeMarkdownUrl", () => {
  it("allows http / https", () => {
    expect(safeMarkdownUrl("http://example.com")).toBe("http://example.com");
    expect(safeMarkdownUrl("https://example.com")).toBe("https://example.com");
  });

  it("allows mailto / tel", () => {
    expect(safeMarkdownUrl("mailto:a@b.com")).toBe("mailto:a@b.com");
    expect(safeMarkdownUrl("tel:+1234")).toBe("tel:+1234");
  });

  it("allows relative path / anchor", () => {
    expect(safeMarkdownUrl("/path")).toBe("/path");
    expect(safeMarkdownUrl("#anchor")).toBe("#anchor");
    expect(safeMarkdownUrl("./rel")).toBe("./rel");
  });

  it("rejects javascript: protocol", () => {
    expect(safeMarkdownUrl("javascript:alert(1)")).toBe("#");
    expect(safeMarkdownUrl("JAVASCRIPT:alert(1)")).toBe("#");
    expect(safeMarkdownUrl(" javascript:alert(1)")).toBe("#");
  });

  it("rejects data: URI", () => {
    expect(safeMarkdownUrl("data:text/html,<script>1</script>")).toBe("#");
  });

  it("rejects vbscript: protocol", () => {
    expect(safeMarkdownUrl("vbscript:msgbox")).toBe("#");
  });
});

describe("safeMarkdownProps wired into ReactMarkdown", () => {
  it("javascript: link href is neutered", () => {
    const { container } = render(
      <ReactMarkdown {...safeMarkdownProps}>{"[click](javascript:alert(1))"}</ReactMarkdown>,
    );
    const a = container.querySelector("a");
    expect(a).not.toBeNull();
    expect(a?.getAttribute("href") ?? "").not.toMatch(/javascript:/i);
  });

  it("normal https link preserved", () => {
    const { container } = render(
      <ReactMarkdown {...safeMarkdownProps}>{"[ok](https://example.com)"}</ReactMarkdown>,
    );
    expect(container.querySelector("a")?.getAttribute("href")).toBe("https://example.com");
  });
});
