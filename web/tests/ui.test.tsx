import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Alert } from "../src/components/ui/alert";
import { Badge } from "../src/components/ui/badge";
import { FilterTabs } from "../src/components/ui/filter-tabs";
import { Input } from "../src/components/ui/input";

describe("ui primitives", () => {
  it("Badge 渲染内容并按 variant 上色", () => {
    const { getByText } = render(<Badge variant="pending">待人工</Badge>);
    const el = getByText("待人工");
    expect(el.className).toContain("status-warning");
  });

  it("Alert 渲染内容", () => {
    const { getByText } = render(<Alert variant="error">出错了</Alert>);
    expect(getByText("出错了").textContent).toBe("出错了");
  });

  it("Input 透传 placeholder 与 onChange", () => {
    const onChange = vi.fn();
    const { getByPlaceholderText } = render(<Input placeholder="工号" onChange={onChange} />);
    fireEvent.change(getByPlaceholderText("工号"), { target: { value: "x" } });
    expect(onChange).toHaveBeenCalled();
  });

  it("FilterTabs 点击触发 onChange，选中项高亮", () => {
    const onChange = vi.fn();
    const { getByText } = render(
      <FilterTabs
        value="a"
        onChange={onChange}
        options={[
          { value: "a", label: "甲" },
          { value: "b", label: "乙" },
        ]}
      />,
    );
    expect(getByText("甲").className).toContain("bg-brand");
    fireEvent.click(getByText("乙"));
    expect(onChange).toHaveBeenCalledWith("b");
  });
});
