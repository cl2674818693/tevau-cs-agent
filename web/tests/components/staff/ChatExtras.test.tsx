// ChatExtras：ChatHeader / EmptyState / LoadingView / ErrorView / StatusBanners / GuestLoginBar
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import {
  ChatHeader,
  EmptyState,
  ErrorView,
  GuestLoginBar,
  LoadingView,
  StatusBanners,
} from "@/components/ChatExtras";
import i18n from "@/i18n";

beforeAll(async () => {
  await i18n.changeLanguage("zh");
});

describe("ChatHeader", () => {
  it("AI 模式：显示 AI 副标题 + 绿色状态点", () => {
    render(<ChatHeader mode="ai" sending={false} onStop={() => {}} userType="b" />);
    expect(screen.getByText(/AI 驅動/)).toBeInTheDocument();
  });

  it("human_pending：显示等待文案", () => {
    render(<ChatHeader mode="human_pending" sending={false} onStop={() => {}} userType="b" />);
    expect(screen.getByText(/等候人工客服/)).toBeInTheDocument();
  });

  it("human_takeover：显示客服署名文案", () => {
    render(
      <ChatHeader
        mode="human_takeover"
        staffName="小王"
        sending={false}
        onStop={() => {}}
        userType="b"
      />,
    );
    expect(screen.getByText(/小王/)).toBeInTheDocument();
  });

  it("sending=true 时显示停止按钮", () => {
    const onStop = vi.fn();
    render(<ChatHeader mode="ai" sending={true} onStop={onStop} userType="b" />);
    fireEvent.click(screen.getByRole("button", { name: "停止生成" }));
    expect(onStop).toHaveBeenCalled();
  });

  it("sending=false 不渲染停止按钮", () => {
    render(<ChatHeader mode="ai" sending={false} onStop={() => {}} userType="b" />);
    expect(screen.queryByRole("button", { name: "停止生成" })).toBeNull();
  });
});

describe("EmptyState", () => {
  it("显示标题 + greeting", () => {
    render(<EmptyState greeting="欢迎语" />);
    expect(screen.getByText(/Tevau 助理/)).toBeInTheDocument();
    expect(screen.getByText("欢迎语")).toBeInTheDocument();
  });
});

describe("LoadingView/ErrorView", () => {
  it("LoadingView 渲染中文 loading 文案", () => {
    render(<LoadingView />);
    expect(screen.getByText(/正在連線/)).toBeInTheDocument();
  });

  it("ErrorView 显示错误文案 + 重试按钮触发回调", () => {
    const onRetry = vi.fn();
    render(<ErrorView onRetry={onRetry} />);
    fireEvent.click(screen.getByRole("button", { name: /重試/ }));
    expect(onRetry).toHaveBeenCalled();
  });
});

describe("GuestLoginBar", () => {
  it("渲染主账户登录链接", () => {
    render(<GuestLoginBar />);
    const link = screen.getByRole("link", { name: /主帳戶登入/ });
    expect(link).toHaveAttribute("href", "/bu/login");
  });
});

describe("StatusBanners", () => {
  it("connection=offline 显示离线条", () => {
    render(<StatusBanners connection="offline" limitPct={0} />);
    expect(screen.getByText(/網路已中斷/)).toBeInTheDocument();
  });

  it("connection=reconnecting 显示重连中文案", () => {
    render(<StatusBanners connection="reconnecting" limitPct={0} />);
    expect(screen.getByText(/正在重新連線/)).toBeInTheDocument();
  });

  it("connection=online 不渲染离线条", () => {
    render(<StatusBanners connection="online" limitPct={0} />);
    expect(screen.queryByText(/網路已中斷/)).toBeNull();
  });

  it("limitPct 介于 80-99 显示配额警告", () => {
    render(<StatusBanners connection="online" limitPct={85} />);
    expect(screen.getByText(/85/)).toBeInTheDocument();
  });

  it("limitPct >= 100 不渲染（已限流，由其它处提示）", () => {
    render(<StatusBanners connection="online" limitPct={100} />);
    expect(screen.queryByText(/100/)).toBeNull();
  });

  it("limitPct < 80 不渲染", () => {
    render(<StatusBanners connection="online" limitPct={50} />);
    expect(screen.queryByText(/今日用量/)).toBeNull();
  });
});
