// AgentRatingPromptToast：工单 resolved/closed 后被动弹满意度评分。
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AgentRatingPromptToast } from "@/components/AgentRatingPromptToast";
import * as rating from "@/api/userAgentRating";

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.restoreAllMocks());

describe("AgentRatingPromptToast", () => {
  it("convId=null：什么都不做", () => {
    const spy = vi.spyOn(rating, "getRatingEligibility");
    const { container } = render(<AgentRatingPromptToast convId={null} ticketEvents={[]} />);
    expect(spy).not.toHaveBeenCalled();
    expect(container.textContent).toBe("");
  });

  it("最新事件非 resolved/closed：不探测、不弹", () => {
    const spy = vi.spyOn(rating, "getRatingEligibility");
    render(
      <AgentRatingPromptToast convId={1} ticketEvents={[{ event: "in_progress" }]} />,
    );
    expect(spy).not.toHaveBeenCalled();
  });

  it("resolved 事件 + eligible：弹出评分", async () => {
    vi.spyOn(rating, "getRatingEligibility").mockResolvedValue({
      eligible: true,
      already_rated: false,
      staff_id: "a",
    });
    render(
      <AgentRatingPromptToast convId={1} ticketEvents={[{ event: "resolved" }]} />,
    );
    await waitFor(() => expect(screen.getByText(/服务已结束/)).toBeInTheDocument());
    const stars = screen.getAllByRole("button", { name: /星/ });
    expect(stars).toHaveLength(5);
  });

  it("closed 事件 + already_rated：不弹", async () => {
    vi.spyOn(rating, "getRatingEligibility").mockResolvedValue({
      eligible: true,
      already_rated: true,
      staff_id: "a",
    });
    const { container } = render(
      <AgentRatingPromptToast convId={1} ticketEvents={[{ event: "closed" }]} />,
    );
    await waitFor(() => expect(rating.getRatingEligibility).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });

  it("点星提交评分 → 调 submitAgentRating + 关闭", async () => {
    vi.spyOn(rating, "getRatingEligibility").mockResolvedValue({
      eligible: true,
      already_rated: false,
      staff_id: "a",
    });
    const sub = vi.spyOn(rating, "submitAgentRating").mockResolvedValue();
    render(
      <AgentRatingPromptToast convId={2} ticketEvents={[{ event: "resolved" }]} />,
    );
    await waitFor(() => expect(screen.getByText(/服务已结束/)).toBeInTheDocument());
    const fourStar = screen.getByRole("button", { name: "4 星" });
    fireEvent.click(fourStar);
    await waitFor(() =>
      expect(sub).toHaveBeenCalledWith(2, expect.objectContaining({ rating: 4 })),
    );
    await waitFor(() => expect(screen.queryByText(/服务已结束/)).toBeNull());
  });

  it("点稍后再说 → 直接关闭", async () => {
    vi.spyOn(rating, "getRatingEligibility").mockResolvedValue({
      eligible: true,
      already_rated: false,
      staff_id: "a",
    });
    render(
      <AgentRatingPromptToast convId={2} ticketEvents={[{ event: "resolved" }]} />,
    );
    await waitFor(() => expect(screen.getByText(/服务已结束/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "稍后再说" }));
    await waitFor(() => expect(screen.queryByText(/服务已结束/)).toBeNull());
  });
});
