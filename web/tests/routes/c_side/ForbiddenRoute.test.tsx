// ForbiddenRoute：纯静态 403 页 + "返回工作台"跳转。
// 用例覆盖：基本渲染 + 跳转目标命中。
import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ForbiddenRoute } from "@/routes/ForbiddenRoute";

import { renderWithRouter } from "../../helpers/render";

describe("ForbiddenRoute", () => {
  it("默认渲染：显示 403 标题与副标题", () => {
    renderWithRouter(<ForbiddenRoute />, { path: "/403" });
    expect(screen.getByText(/403/)).toBeInTheDocument();
    expect(screen.getByText("您当前角色无法访问此页面")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /返回工作台/ })).toBeInTheDocument();
  });

  it("点击「返回工作台」跳到 /staff/conversations", () => {
    renderWithRouter(<ForbiddenRoute />, {
      initialPath: "/403",
      path: "/403",
      extraRoutes: [
        {
          path: "/staff/conversations",
          element: <div data-testid="conv-list-stub">CONV_LIST</div>,
        },
      ],
    });

    fireEvent.click(screen.getByRole("button", { name: /返回工作台/ }));
    expect(screen.getByTestId("conv-list-stub")).toBeInTheDocument();
  });
});
