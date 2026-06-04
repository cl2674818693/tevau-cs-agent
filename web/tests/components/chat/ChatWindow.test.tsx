// ChatWindow：基于 useChat 状态机的整页。loading / error / empty / 主流程渲染。
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// 用 vi.mock 整体替换 useChat / useTicketStream / userType / api，避免真实网络。
const useChatMock = vi.fn();
vi.mock("@/hooks/useChat", () => ({
  useChat: () => useChatMock(),
}));

const useTicketStreamMock = vi.fn<
  () => Array<{ event: string; external_id?: string; comment?: string; actor?: string }>
>(() => []);
vi.mock("@/hooks/useTicketStream", () => ({
  useTicketStream: () => useTicketStreamMock(),
}));

vi.mock("@/hooks/useVisualViewport", () => ({
  useKeyboardInset: () => 0,
}));

const userTypeMock = vi.fn(() => "c");
vi.mock("@/api/identity", () => ({
  userType: () => userTypeMock(),
  AuthExpiredError: class extends Error {},
}));

vi.mock("@/api/chat", () => ({
  sendFeedback: vi.fn(),
  sendTicketUserEvent: vi.fn(),
}));

vi.mock("@/api/attachments", () => ({
  attachmentUrl: (cid: number, id: number) => `/api/v1/conversations/${cid}/attachments/${id}`,
  uploadAttachment: async () => 1,
  resolveAttachmentSrc: async () => "blob:fake",
}));

vi.mock("@/api/userAgentRating", () => ({
  getRatingEligibility: async () => ({
    eligible: false,
    already_rated: false,
    staff_id: null,
  }),
  submitAgentRating: async () => {},
}));

import { ChatWindow } from "@/components/ChatWindow";

const INIT: {
  conversation_id: number;
  user_type: "c" | "b" | "g";
  display_name: string;
  greeting: string;
  mode: "ai";
  history_url: null;
  limits: { daily_token_used_pct: number; max_turns: number };
} = {
  conversation_id: 1,
  user_type: "c",
  display_name: "U",
  greeting: "你好",
  mode: "ai",
  history_url: null,
  limits: { daily_token_used_pct: 0, max_turns: 30 },
};

function baseChat(over: Partial<ReturnType<typeof base>> = {}) {
  return { ...base(), ...over };
}
function base() {
  return {
    // greeting 不再塞 messages；EmptyState 由 messages.length === 0 触发
    messages: [] as Array<{ role: string; content: string }>,
    sending: false,
    mode: "ai",
    staffName: undefined as string | undefined,
    status: "ready" as "ready" | "loading" | "error",
    connection: "online" as "online" | "offline" | "reconnecting",
    limitPct: 0,
    rateLimited: false,
    send: vi.fn(),
    requestHandoff: vi.fn(),
    stop: vi.fn(),
    init: INIT as null | typeof INIT,
    retryInit: vi.fn(),
  };
}

describe("ChatWindow", () => {
  beforeEach(() => {
    useChatMock.mockReset();
    useTicketStreamMock.mockReset().mockReturnValue([]);
    userTypeMock.mockReset().mockReturnValue("c");
  });
  afterEach(() => vi.restoreAllMocks());

  it("loading 状态：显示 LoadingView", () => {
    useChatMock.mockReturnValue(baseChat({ status: "loading", init: null }));
    render(<ChatWindow />);
    expect(screen.getByText(/正在連線/)).toBeInTheDocument();
  });

  it("error 状态：显示 ErrorView + 点重试调 retryInit", async () => {
    const ch = baseChat({ status: "error", init: null });
    useChatMock.mockReturnValue(ch);
    render(<ChatWindow />);
    expect(screen.getByText(/連線失敗/)).toBeInTheDocument();
    const btn = screen.getByRole("button", { name: /重試/ });
    btn.click();
    await waitFor(() => expect(ch.retryInit).toHaveBeenCalled());
  });

  it("ready + 空 messages + mode=ai → EmptyState（不渲染 MessageList）", () => {
    useChatMock.mockReturnValue(baseChat());
    render(<ChatWindow />);
    // emptyTitle 出现
    expect(screen.getByText(/Tevau 助理/)).toBeInTheDocument();
    // C 端 emptyHint
    expect(screen.getByText(/帳戶、卡片、交易紀錄/)).toBeInTheDocument();
    expect(screen.queryByRole("log")).toBeNull();
  });

  it("ready + 已开始对话：渲染 MessageList + Handoff 入口", () => {
    useChatMock.mockReturnValue(
      baseChat({
        messages: [
          { role: "user", content: "我有问题" },
          { role: "assistant", content: "请讲" },
        ],
      }),
    );
    render(<ChatWindow />);
    expect(screen.getByRole("log")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /尚未解決/ })).toBeInTheDocument();
  });

  it("sending=true 时隐藏 Handoff 入口", () => {
    useChatMock.mockReturnValue(
      baseChat({
        sending: true,
        messages: [
          { role: "system", content: "g" },
          { role: "user", content: "q" },
        ],
      }),
    );
    render(<ChatWindow />);
    expect(screen.queryByRole("button", { name: /尚未解決/ })).toBeNull();
  });

  it("connection=offline：显示离线条", () => {
    useChatMock.mockReturnValue(baseChat({ connection: "offline" }));
    render(<ChatWindow />);
    expect(screen.getByText(/網路已中斷/)).toBeInTheDocument();
  });

  it("limitPct >= 80 且 < 100：显示配额警告", () => {
    useChatMock.mockReturnValue(baseChat({ limitPct: 90 }));
    render(<ChatWindow />);
    expect(screen.getByText(/90/)).toBeInTheDocument();
  });

  it("user_type=g：显示游客登录条", () => {
    useChatMock.mockReturnValue(
      baseChat({ init: { ...INIT, user_type: "g" } }),
    );
    render(<ChatWindow />);
    expect(screen.getByRole("link", { name: /主帳戶登入/ })).toBeInTheDocument();
  });

  it("rateLimited=true：输入框 placeholder 切到限流提示", () => {
    useChatMock.mockReturnValue(baseChat({ rateLimited: true }));
    render(<ChatWindow />);
    expect(screen.getByPlaceholderText(/請求過於頻繁/)).toBeInTheDocument();
  });

  it("mode=human_takeover / human_pending：placeholder 切到留言语义", () => {
    for (const mode of ["human_takeover", "human_pending"] as const) {
      useChatMock.mockReturnValue(baseChat({ mode, staffName: "小王" }));
      const { unmount } = render(<ChatWindow />);
      expect(screen.getByPlaceholderText(/繼續補充|補充資訊/)).toBeInTheDocument();
      unmount();
    }
  });

  it("切语言后 inputPlaceholder/EmptyState 跟随更新（不再卡住英文兜底）", async () => {
    const { default: i18n } = await import("@/i18n");
    useChatMock.mockReturnValue(baseChat());
    render(<ChatWindow />);
    // 默认 zh：placeholder = 描述您的問題…；emptyHint = 帳戶/卡片
    expect(screen.getByPlaceholderText(/描述您的問題/)).toBeInTheDocument();
    expect(screen.getByText(/帳戶、卡片、交易紀錄/)).toBeInTheDocument();
    // 切到 en
    await i18n.changeLanguage("en");
    expect(screen.getByPlaceholderText(/Describe your issue/)).toBeInTheDocument();
    expect(screen.getByText(/Ask me anything about your account/)).toBeInTheDocument();
    // 复位
    await i18n.changeLanguage("zh");
  });

  it("ticket 事件：banner 渲染 + resolved ticket 显示确认卡片", () => {
    useTicketStreamMock.mockReturnValue([
      { event: "resolved", external_id: "T-1", comment: "完成" },
    ]);
    useChatMock.mockReturnValue(baseChat());
    render(<ChatWindow />);
    // TicketStatusBanner 文案
    expect(screen.getByText(/工單已解決/)).toBeInTheDocument();
    // TicketCard summary
    expect(screen.getByText("完成")).toBeInTheDocument();
  });
});
