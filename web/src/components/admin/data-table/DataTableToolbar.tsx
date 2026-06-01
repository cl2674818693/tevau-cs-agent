import { X } from "lucide-react";
import type { Table } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function DataTableToolbar<TData>({
  table, searchColumn, placeholder = "搜索…",
  children,
}: {
  table: Table<TData>;
  searchColumn?: string;
  placeholder?: string;
  children?: React.ReactNode;
}) {
  const filterColumn = searchColumn ? table.getColumn(searchColumn) : null;
  const isFiltered = table.getState().columnFilters.length > 0;
  return (
    <div className="flex items-center gap-2">
      {filterColumn && (
        <Input
          placeholder={placeholder}
          value={(filterColumn.getFilterValue() as string) ?? ""}
          onChange={(e) => filterColumn.setFilterValue(e.target.value)}
          className="h-8 w-[200px]"
        />
      )}
      {children}
      {isFiltered && (
        <Button variant="ghost" size="sm" onClick={() => table.resetColumnFilters()}>
          清除 <X className="ml-1 h-3 w-3" />
        </Button>
      )}
    </div>
  );
}
