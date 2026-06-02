// SubjectInfoCard：调 getSubjectInfo 显示用户信息卡。
// 关键场景：未登录态 / 加载态 / 已加载完整 / 部分字段空 / 业务库失败 / 仅 client_info。
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/staffFetch", () => ({
  staffFetch: vi.fn(),
}));

import { SubjectInfoCard } from "@/components/SubjectInfoCard";
import * as staffApi from "@/api/staff";

describe("SubjectInfoCard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => vi.restoreAllMocks());

  it("token=null 时不发起请求并保持 loading", () => {
    const spy = vi.spyOn(staffApi, "getSubjectInfo");
    render(<SubjectInfoCard token={null} convId={1} />);
    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByText("用户信息")).toBeInTheDocument();
  });

  it("加载态：显示骨架 loading 标题", () => {
    vi.spyOn(staffApi, "getSubjectInfo").mockReturnValue(new Promise(() => {}));
    render(<SubjectInfoCard token="tk" convId={1} />);
    expect(screen.getByText("用户信息")).toBeInTheDocument();
  });

  it("拉取失败：显示错误提示", async () => {
    vi.spyOn(staffApi, "getSubjectInfo").mockRejectedValue(new Error("net"));
    render(<SubjectInfoCard token="tk" convId={1} />);
    await waitFor(() => expect(screen.getByText(/拉取用户信息失败/)).toBeInTheDocument());
  });

  it("C 端用户：显示昵称/UC/手机/邮箱/状态/KYC", async () => {
    vi.spyOn(staffApi, "getSubjectInfo").mockResolvedValue({
      subject: {
        user_type: "c",
        subject_id: "u-1",
        found: true,
        nick_name: "张三",
        user_code: "UC123",
        phone: "139****1234",
        email: "u@example.com",
        user_status: "正常",
        kyc_status: "已认证",
        open_card_status: "已开",
        registration_time: "2024-01-01 10:00:00",
        last_login_time: "2024-06-01 12:00:00",
        recent_30d_transactions: [{ currency: "USD", count: 3, amount: "100.50" }],
      },
      client_info: null,
    });
    render(<SubjectInfoCard token="tk" convId={1} />);
    await waitFor(() => expect(screen.getByText("张三")).toBeInTheDocument());
    expect(screen.getByText("UC123")).toBeInTheDocument();
    expect(screen.getByText("139****1234")).toBeInTheDocument();
    expect(screen.getByText("u@example.com")).toBeInTheDocument();
    expect(screen.getByText("正常")).toBeInTheDocument();
    expect(screen.getByText("已认证")).toBeInTheDocument();
    expect(screen.getByText("2024-01-01")).toBeInTheDocument(); // 只显示日期部分
    // 交易行
    expect(screen.getByText(/USD 3笔/)).toBeInTheDocument();
  });

  it("C 端部分字段缺失：用占位符 — 兜底", async () => {
    vi.spyOn(staffApi, "getSubjectInfo").mockResolvedValue({
      subject: { user_type: "c", subject_id: "u-1", found: true },
      client_info: null,
    });
    render(<SubjectInfoCard token="tk" convId={1} />);
    // 多个 — 占位
    await waitFor(() => expect(screen.getAllByText("—").length).toBeGreaterThan(0));
    // 30天交易缺省提示
    expect(screen.getByText(/近 30 天无成功交易/)).toBeInTheDocument();
  });

  it("B 端用户：显示公司名 / tenant / 状态", async () => {
    vi.spyOn(staffApi, "getSubjectInfo").mockResolvedValue({
      subject: {
        user_type: "b",
        subject_id: "bu-1",
        found: true,
        company_name: "示例科技",
        tenant_id: "T-001",
        status: "运行中",
      },
      client_info: null,
    });
    render(<SubjectInfoCard token="tk" convId={1} />);
    await waitFor(() => expect(screen.getByText("示例科技")).toBeInTheDocument());
    expect(screen.getByText("T-001")).toBeInTheDocument();
    expect(screen.getByText("运行中")).toBeInTheDocument();
  });

  it("found=false：显示'业务库未关联或主体不存在'，仍展示 client_info", async () => {
    vi.spyOn(staffApi, "getSubjectInfo").mockResolvedValue({
      subject: { user_type: "c", subject_id: "u-1", found: false },
      client_info: {
        platform: "iOS",
        app_version: "2.0.1",
        user_agent: "Mozilla/5.0 (iPhone)",
        updated_at: "2024-01-01",
      },
    });
    render(<SubjectInfoCard token="tk" convId={1} />);
    await waitFor(() =>
      expect(screen.getByText(/业务库未关联或主体不存在/)).toBeInTheDocument(),
    );
    expect(screen.getByText("iOS")).toBeInTheDocument();
    expect(screen.getByText("2.0.1")).toBeInTheDocument();
  });

  it("UA 过长时截断为前 40 字符 + …", async () => {
    const long = "Mozilla/5.0 ".repeat(20);
    vi.spyOn(staffApi, "getSubjectInfo").mockResolvedValue({
      subject: { user_type: "c", subject_id: "u-1", found: false },
      client_info: {
        platform: null,
        app_version: null,
        user_agent: long,
        updated_at: "2024-01-01",
      },
    });
    render(<SubjectInfoCard token="tk" convId={1} />);
    await waitFor(() => expect(screen.getByText(/Mozilla\/5.0/)).toBeInTheDocument());
    expect(screen.getByText(/…$/)).toBeInTheDocument();
  });

  it("convId 变更：重新拉取", async () => {
    const spy = vi.spyOn(staffApi, "getSubjectInfo").mockResolvedValue({
      subject: { user_type: "c", subject_id: "u-1", found: true, nick_name: "A" },
      client_info: null,
    });
    const { rerender } = render(<SubjectInfoCard token="tk" convId={1} />);
    await waitFor(() => expect(spy).toHaveBeenCalledWith("tk", 1));
    spy.mockClear();
    spy.mockResolvedValueOnce({
      subject: { user_type: "c", subject_id: "u-2", found: true, nick_name: "B" },
      client_info: null,
    });
    rerender(<SubjectInfoCard token="tk" convId={2} />);
    await waitFor(() => expect(spy).toHaveBeenCalledWith("tk", 2));
  });
});
