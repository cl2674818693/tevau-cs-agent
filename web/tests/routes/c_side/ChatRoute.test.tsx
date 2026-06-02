// ChatRoute：C 端聊天页（嵌 APP 的 H5）。
// 仅测路由组件自身职责：
//  - 移除 html.dark class（避免 admin 暗色泄漏到 H5）
//  - loadResumeContext 拿到 resume 后把 convId 透传给 AgentRatingButton
//  - 未续接（resume=null）时 convId 保持 null
// ChatWindow 和 AgentRatingButton 整组 mock，避免引入 useChat / SSE / bridge 全链路。

import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 必须在 import ChatRoute 之前 mock，以拦截其依赖
vi.mock("@/components/ChatWindow", () => ({
  ChatWindow: () => <div data-testid="chat-window-stub">ChatWindow</div>,
}));

vi.mock("@/components/AgentRatingButton", () => ({
  AgentRatingButton: ({ conversationId }: { conversationId: number | null }) => (
    <div data-testid="agent-rating-stub">conv:{String(conversationId)}</div>
  ),
}));

const { loadResumeContextMock } = vi.hoisted(() => ({
  loadResumeContextMock: vi.fn(),
}));
vi.mock("@/lib/chatSession", () => ({
  loadResumeContext: () => loadResumeContextMock(),
}));

import { ChatRoute } from "@/routes/ChatRoute";

import { renderWithRouter } from "../../helpers/render";

describe("ChatRoute", () => {
  beforeEach(() => {
    document.documentElement.classList.add("dark");
    loadResumeContextMock.mockReset();
  });
  afterEach(() => {
    document.documentElement.classList.remove("dark");
    vi.restoreAllMocks();
  });

  it("挂载即移除 html.dark class", async () => {
    loadResumeContextMock.mockResolvedValue({ sessionId: null, resume: undefined });
    renderWithRouter(<ChatRoute />, { path: "/" });
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("无续接：AgentRatingButton 收到 conversationId=null", async () => {
    loadResumeContextMock.mockResolvedValue({ sessionId: null, resume: undefined });
    renderWithRouter(<ChatRoute />, { path: "/" });
    expect(await screen.findByTestId("chat-window-stub")).toBeInTheDocument();
    expect(screen.getByTestId("agent-rating-stub")).toHaveTextContent("conv:null");
  });

  it("有续接：拿到的 resume 透传给 AgentRatingButton", async () => {
    loadResumeContextMock.mockResolvedValue({ sessionId: "s1", resume: 7777 });
    renderWithRouter(<ChatRoute />, { path: "/" });
    await waitFor(() =>
      expect(screen.getByTestId("agent-rating-stub")).toHaveTextContent("conv:7777"),
    );
  });

  it("loadResumeContext reject 时静默：convId 维持 null，不崩", async () => {
    loadResumeContextMock.mockRejectedValue(new Error("boom"));
    renderWithRouter(<ChatRoute />, { path: "/" });
    expect(await screen.findByTestId("chat-window-stub")).toBeInTheDocument();
    // 等一帧让 promise reject 跑完
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.getByTestId("agent-rating-stub")).toHaveTextContent("conv:null");
  });
});
