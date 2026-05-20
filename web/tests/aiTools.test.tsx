import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { runAiTool } from "../src/api/staff";
import { AiToolsPanel } from "../src/components/AiToolsPanel";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (_url: string, _opts?: RequestInit) =>
        new Response(JSON.stringify({ ok: true, data: { masked_phone: "138****78" } }), {
          status: 200,
        }),
    ),
  );
});
afterEach(() => vi.restoreAllMocks());

describe("runAiTool", () => {
  it("posts params to the tool endpoint", async () => {
    const out = await runAiTool("t", 4, "query_user", { user_id: "U1" });
    expect(out.ok).toBe(true);
    const [url, opts] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toBe("/staff/api/v1/conversations/4/ai-tools/query_user");
    expect(JSON.parse((opts as RequestInit).body as string)).toEqual({
      params: { user_id: "U1" },
    });
  });

  it("returns error object on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("nope", { status: 403 })),
    );
    const out = await runAiTool("t", 4, "query_user", {});
    expect(out.ok).toBe(false);
    expect(out.error).toContain("403");
  });
});

describe("AiToolsPanel", () => {
  it("runs tool and shows masked result", async () => {
    render(<AiToolsPanel token="t" convId={4} />);
    fireEvent.click(screen.getByText("运行"));
    await waitFor(() => expect(screen.getByText(/138\*\*\*\*78/)).toBeTruthy());
  });

  it("rejects invalid JSON params without calling fetch", () => {
    render(<AiToolsPanel token="t" convId={4} />);
    const ta = screen.getByLabelText("工具参数 JSON") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "{不是json" } });
    fireEvent.click(screen.getByText("运行"));
    expect(screen.getByText("参数不是合法 JSON")).toBeTruthy();
    expect(fetch as unknown as ReturnType<typeof vi.fn>).not.toHaveBeenCalled();
  });
});
