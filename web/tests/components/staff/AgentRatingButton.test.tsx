// AgentRatingButton：仅在 eligible && !already_rated 时显示；点开评分对话框，提交。
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentRatingButton } from "@/components/AgentRatingButton";
import * as rating from "@/api/userAgentRating";

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.restoreAllMocks());

describe("AgentRatingButton", () => {
  it("convId=null：完全不渲染", () => {
    const { container } = render(<AgentRatingButton conversationId={null} />);
    expect(container.textContent).toBe("");
  });

  it("convId<=0：跳过 eligibility 探测，不渲染", () => {
    const spy = vi.spyOn(rating, "getRatingEligibility");
    render(<AgentRatingButton conversationId={0} />);
    expect(spy).not.toHaveBeenCalled();
  });

  it("eligible=false：不渲染按钮", async () => {
    vi.spyOn(rating, "getRatingEligibility").mockResolvedValue({
      eligible: false,
      already_rated: false,
      staff_id: null,
    });
    const { container } = render(<AgentRatingButton conversationId={1} />);
    await waitFor(() => expect(rating.getRatingEligibility).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });

  it("already_rated=true：不渲染按钮", async () => {
    vi.spyOn(rating, "getRatingEligibility").mockResolvedValue({
      eligible: true,
      already_rated: true,
      staff_id: "a",
    });
    const { container } = render(<AgentRatingButton conversationId={1} />);
    await waitFor(() => expect(rating.getRatingEligibility).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });

  it("eligible：显示评价按钮 → 打开对话框 → 提交评分 → 关闭并隐藏", async () => {
    vi.spyOn(rating, "getRatingEligibility").mockResolvedValue({
      eligible: true,
      already_rated: false,
      staff_id: "a",
    });
    const submit = vi
      .spyOn(rating, "submitAgentRating")
      .mockResolvedValue(undefined);
    render(<AgentRatingButton conversationId={1} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "评价客服" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "评价客服" }));
    // 提交按钮在对话框里
    fireEvent.click(screen.getByRole("button", { name: "提交" }));
    await waitFor(() => expect(submit).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "评价客服" })).toBeNull(),
    );
  });

  it("点击星标改变评分（默认 5 星）", async () => {
    vi.spyOn(rating, "getRatingEligibility").mockResolvedValue({
      eligible: true,
      already_rated: false,
      staff_id: "a",
    });
    const submit = vi.spyOn(rating, "submitAgentRating").mockResolvedValue();
    render(<AgentRatingButton conversationId={5} />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "评价客服" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "评价客服" }));
    // 改成 3 星：点第 3 个 radio
    const stars = screen.getAllByRole("radio");
    fireEvent.click(stars[2]);
    fireEvent.click(screen.getByRole("button", { name: "提交" }));
    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith(5, expect.objectContaining({ rating: 3 })),
    );
  });

  it("提交失败时显示错误，不关闭对话框", async () => {
    vi.spyOn(rating, "getRatingEligibility").mockResolvedValue({
      eligible: true,
      already_rated: false,
      staff_id: "a",
    });
    vi.spyOn(rating, "submitAgentRating").mockRejectedValue(new Error("400"));
    render(<AgentRatingButton conversationId={5} />);
    await waitFor(() => screen.getByRole("button", { name: "评价客服" }));
    fireEvent.click(screen.getByRole("button", { name: "评价客服" }));
    fireEvent.click(screen.getByRole("button", { name: "提交" }));
    await waitFor(() => expect(screen.getByText("400")).toBeInTheDocument());
    // 对话框仍在
    expect(screen.getByRole("button", { name: "提交" })).toBeInTheDocument();
  });
});
