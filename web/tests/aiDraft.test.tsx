import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  approveAiDraft,
  disableAiDraft,
  enableAiDraft,
  rejectAiDraft,
  type StaffStreamEvent,
} from "../src/api/staff";
import { AiDraftPanel } from "../src/components/AiDraftPanel";
import { useAiDraft } from "../src/hooks/useAiDraft";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, _opts?: RequestInit) => new Response("{}", { status: 200 })),
  );
});
afterEach(() => vi.restoreAllMocks());

describe("api/staff ai-draft", () => {
  it("enable/disable/approve/reject hit the right endpoints", async () => {
    await enableAiDraft("t", 5);
    await disableAiDraft("t", 5);
    await approveAiDraft("t", 5);
    await rejectAiDraft("t", 5, "改写内容");
    const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.map((c) => c[0]);
    expect(calls).toEqual([
      "/staff/api/v1/conversations/5/ai-draft/enable",
      "/staff/api/v1/conversations/5/ai-draft/disable",
      "/staff/api/v1/conversations/5/ai-draft/approve",
      "/staff/api/v1/conversations/5/ai-draft/reject",
    ]);
    const rejectBody = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[3][1].body;
    expect(JSON.parse(rejectBody)).toEqual({ rewrite: "改写内容" });
  });
});

describe("AiDraftPanel", () => {
  it("renders nothing without a draft", () => {
    const { container } = render(
      <AiDraftPanel draft={null} onApprove={vi.fn()} onReject={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("approve calls onApprove", () => {
    const onApprove = vi.fn();
    render(<AiDraftPanel draft="草稿X" onApprove={onApprove} onReject={vi.fn()} />);
    expect(screen.getByText("草稿X")).toBeTruthy();
    fireEvent.click(screen.getByText("直接发出"));
    expect(onApprove).toHaveBeenCalled();
  });

  it("rewrite flow calls onReject with edited text", () => {
    const onReject = vi.fn();
    render(<AiDraftPanel draft="原草稿" onApprove={vi.fn()} onReject={onReject} />);
    fireEvent.click(screen.getByText("改写"));
    const ta = screen.getByRole("textbox") as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: "新内容" } });
    fireEvent.click(screen.getByText("改写后发送"));
    expect(onReject).toHaveBeenCalledWith("新内容");
  });
});

describe("useAiDraft", () => {
  it("picks up latest ai_draft_ready event", () => {
    const events: StaffStreamEvent[] = [
      { type: "ai_draft_ready", draft: "草稿1" },
      { type: "user_message", content: "x" },
      { type: "ai_draft_ready", draft: "草稿2" },
    ];
    const { result } = renderHook(() => useAiDraft("t", 9, events));
    expect(result.current.aiDraft).toBe("草稿2");
  });

  it("toggleDraftMode flips mode and returns notice", async () => {
    const { result } = renderHook(() => useAiDraft("t", 9, []));
    let msg = "";
    await act(async () => {
      msg = await result.current.toggleDraftMode();
    });
    expect(result.current.draftMode).toBe(true);
    expect(msg).toContain("开启");
  });

  it("approve clears the draft", async () => {
    const events: StaffStreamEvent[] = [{ type: "ai_draft_ready", draft: "草稿" }];
    const { result } = renderHook(() => useAiDraft("t", 9, events));
    expect(result.current.aiDraft).toBe("草稿");
    await act(async () => {
      await result.current.approve();
    });
    expect(result.current.aiDraft).toBeNull();
  });
});
