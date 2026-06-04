import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { App as AntApp } from "antd";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { PresenceToggle } from "../../src/components/PresenceToggle";
import * as api from "../../src/api/staffPresence";

const renderWith = (ui: React.ReactNode) =>
  render(<AntApp>{ui}</AntApp>);

describe("PresenceToggle", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("登录默认 offline", () => {
    renderWith(<PresenceToggle token="t" />);
    expect(screen.getByRole("switch")).not.toBeChecked();
    expect(screen.getByText(/离线/)).toBeInTheDocument();
  });

  it("点开 → 调 postPresence(online) → 切换显示", async () => {
    vi.spyOn(api, "postPresence").mockResolvedValue({ ok: true, released_count: 0 });
    renderWith(<PresenceToggle token="t" />);
    fireEvent.click(screen.getByRole("switch"));
    await waitFor(() =>
      expect(api.postPresence).toHaveBeenCalledWith("t", "online"),
    );
    expect(screen.getByText(/在线/)).toBeInTheDocument();
  });

  it("从 online 关到 offline，released_count>0 时弹提示", async () => {
    vi.spyOn(api, "postPresence")
      .mockResolvedValueOnce({ ok: true, released_count: 0 })
      .mockResolvedValueOnce({ ok: true, released_count: 2 });
    renderWith(<PresenceToggle token="t" />);
    fireEvent.click(screen.getByRole("switch"));
    await waitFor(() => expect(screen.getByText(/在线/)).toBeInTheDocument());
    fireEvent.click(screen.getByRole("switch"));
    await waitFor(() =>
      expect(screen.getByText(/已释放 2 个未接管会话给其他客服/)).toBeInTheDocument(),
    );
  });
});
