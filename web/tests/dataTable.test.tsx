import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/admin/data-table/DataTable";

type Row = { id: number; name: string };
const cols: ColumnDef<Row>[] = [
  { accessorKey: "id", header: "ID" },
  { accessorKey: "name", header: "Name" },
];
const data: Row[] = Array.from({ length: 25 }, (_, i) => ({ id: i + 1, name: `n${i}` }));

describe("DataTable", () => {
  it("渲染 + 默认分页 10 条", () => {
    render(<DataTable columns={cols} data={data} />);
    expect(screen.getByText("ID")).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(1 + 10);
  });

  it("翻页", () => {
    render(<DataTable columns={cols} data={data} />);
    fireEvent.click(screen.getByLabelText("下一页"));
    expect(screen.getAllByRole("row")).toHaveLength(1 + 10);
    expect(screen.queryByText("n0")).not.toBeInTheDocument();
  });
});
