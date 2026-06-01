import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import type { Table } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

export function DataTablePagination<TData>({ table }: { table: Table<TData> }) {
  return (
    <div className="flex items-center justify-between px-2">
      <div className="text-xs text-muted-foreground">
        共 {table.getFilteredRowModel().rows.length} 条
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs">每页</span>
          <Select
            value={`${table.getState().pagination.pageSize}`}
            onValueChange={(v) => table.setPageSize(Number(v))}
          >
            <SelectTrigger className="h-7 w-[70px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              {[10, 20, 50, 100].map((p) => (
                <SelectItem key={p} value={`${p}`}>{p}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="text-xs">
          {table.getState().pagination.pageIndex + 1} / {table.getPageCount() || 1}
        </div>
        <div className="flex gap-1">
          <Button variant="outline" size="icon" className="h-7 w-7"
            onClick={() => table.setPageIndex(0)} disabled={!table.getCanPreviousPage()} aria-label="首页">
            <ChevronsLeft className="h-3.5 w-3.5" />
          </Button>
          <Button variant="outline" size="icon" className="h-7 w-7"
            onClick={() => table.previousPage()} disabled={!table.getCanPreviousPage()} aria-label="上一页">
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          <Button variant="outline" size="icon" className="h-7 w-7"
            onClick={() => table.nextPage()} disabled={!table.getCanNextPage()} aria-label="下一页">
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
          <Button variant="outline" size="icon" className="h-7 w-7"
            onClick={() => table.setPageIndex(table.getPageCount() - 1)} disabled={!table.getCanNextPage()} aria-label="末页">
            <ChevronsRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
