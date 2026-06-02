// useAiDraft：开关 + 监听 ai_draft_ready + approve/reject 后不"幽灵复活"旧草稿。
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as staffApi from "@/api/staff";
import { useAiDraft } from "@/hooks/useAiDraft";

describe("useAiDraft", () => {
  beforeEach(() => {
    vi.spyOn(staffApi, "enableAiDraft").mockResolvedValue();
    vi.spyOn(staffApi, "disableAiDraft").mockResolvedValue();
    vi.spyOn(staffApi, "approveAiDraft").mockResolvedValue();
    vi.spyOn(staffApi, "rejectAiDraft").mockResolvedValue();
  });
  afterEach(() => vi.restoreAllMocks());

  it("默认 draftMode=false / aiDraft=null", () => {
    const { result } = renderHook(() => useAiDraft("tk", 1, []));
    expect(result.current.draftMode).toBe(false);
    expect(result.current.aiDraft).toBeNull();
  });

  it("toggleDraftMode 打开 → 调 enable + 返回提示文案", async () => {
    const { result } = renderHook(() => useAiDraft("tk", 1, []));
    let msg = "";
    await act(async () => {
      msg = await result.current.toggleDraftMode();
    });
    expect(staffApi.enableAiDraft).toHaveBeenCalledWith("tk", 1);
    expect(result.current.draftMode).toBe(true);
    expect(msg).toContain("开启");
  });

  it("toggleDraftMode 关闭 → 调 disable + 清草稿", async () => {
    const { result, rerender } = renderHook(
      ({ evs }: { evs: staffApi.StaffStreamEvent[] }) => useAiDraft("tk", 1, evs),
      { initialProps: { evs: [] } },
    );
    await act(async () => {
      await result.current.toggleDraftMode(); // 先开
    });
    // 推入草稿
    rerender({ evs: [{ type: "ai_draft_ready", draft: "hello" } as staffApi.StaffStreamEvent] });
    await waitFor(() => expect(result.current.aiDraft).toBe("hello"));
    let msg = "";
    await act(async () => {
      msg = await result.current.toggleDraftMode();
    });
    expect(staffApi.disableAiDraft).toHaveBeenCalledWith("tk", 1);
    expect(result.current.draftMode).toBe(false);
    expect(result.current.aiDraft).toBeNull();
    expect(msg).toContain("关闭");
  });

  it("接 ai_draft_ready 事件 → aiDraft 更新", async () => {
    const { result, rerender } = renderHook(
      ({ evs }: { evs: staffApi.StaffStreamEvent[] }) => useAiDraft("tk", 1, evs),
      { initialProps: { evs: [] } },
    );
    rerender({ evs: [{ type: "ai_draft_ready", draft: "草稿一" } as staffApi.StaffStreamEvent] });
    await waitFor(() => expect(result.current.aiDraft).toBe("草稿一"));
  });

  it("取 events 末尾最近一条 ai_draft_ready（忽略前面的）", async () => {
    const evs: staffApi.StaffStreamEvent[] = [
      { type: "ai_draft_ready", draft: "旧" } as staffApi.StaffStreamEvent,
      { type: "user_message", content: "u" } as staffApi.StaffStreamEvent,
      { type: "ai_draft_ready", draft: "新" } as staffApi.StaffStreamEvent,
    ];
    const { result } = renderHook(() => useAiDraft("tk", 1, evs));
    await waitFor(() => expect(result.current.aiDraft).toBe("新"));
  });

  it("approve 之后再有非草稿事件不会让已消费草稿复活", async () => {
    const events: staffApi.StaffStreamEvent[] = [
      { type: "ai_draft_ready", draft: "x" } as staffApi.StaffStreamEvent,
    ];
    const { result, rerender } = renderHook(
      ({ evs }: { evs: staffApi.StaffStreamEvent[] }) => useAiDraft("tk", 1, evs),
      { initialProps: { evs: events } },
    );
    await waitFor(() => expect(result.current.aiDraft).toBe("x"));
    await act(async () => {
      await result.current.approve();
    });
    expect(staffApi.approveAiDraft).toHaveBeenCalled();
    expect(result.current.aiDraft).toBeNull();
    // 再推一条普通事件（events 数组引用变化），不应让 "x" 复活
    rerender({
      evs: [...events, { type: "assistant_message", content: "y" } as staffApi.StaffStreamEvent],
    });
    await waitFor(() => expect(result.current.aiDraft).toBeNull());
  });

  it("approve 失败 → 草稿保留以便重试，并触发 onNotice", async () => {
    (staffApi.approveAiDraft as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("net"));
    const notice = vi.fn();
    const evs: staffApi.StaffStreamEvent[] = [
      { type: "ai_draft_ready", draft: "x" } as staffApi.StaffStreamEvent,
    ];
    const { result } = renderHook(() => useAiDraft("tk", 1, evs, notice));
    await waitFor(() => expect(result.current.aiDraft).toBe("x"));
    await act(async () => {
      await result.current.approve();
    });
    expect(notice).toHaveBeenCalledWith(expect.stringContaining("失败"));
    expect(result.current.aiDraft).toBe("x"); // 仍保留
  });

  it("reject 调 rejectAiDraft 带改写内容 + 清草稿", async () => {
    const evs: staffApi.StaffStreamEvent[] = [
      { type: "ai_draft_ready", draft: "原" } as staffApi.StaffStreamEvent,
    ];
    const { result } = renderHook(() => useAiDraft("tk", 1, evs));
    await waitFor(() => expect(result.current.aiDraft).toBe("原"));
    await act(async () => {
      await result.current.reject("改写后的内容");
    });
    expect(staffApi.rejectAiDraft).toHaveBeenCalledWith("tk", 1, "改写后的内容");
    expect(result.current.aiDraft).toBeNull();
  });

  it("token=null 时所有动作都短路", async () => {
    const { result } = renderHook(() => useAiDraft(null, 1, []));
    let msg = "";
    await act(async () => {
      msg = await result.current.toggleDraftMode();
    });
    expect(msg).toBe("");
    await act(async () => {
      await result.current.approve();
    });
    expect(staffApi.approveAiDraft).not.toHaveBeenCalled();
  });

  it("toggle 异常时返回错误提示", async () => {
    (staffApi.enableAiDraft as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error("boom"));
    const { result } = renderHook(() => useAiDraft("tk", 1, []));
    let msg = "";
    await act(async () => {
      msg = await result.current.toggleDraftMode();
    });
    expect(msg).toContain("失败");
    expect(result.current.draftMode).toBe(false);
  });
});
