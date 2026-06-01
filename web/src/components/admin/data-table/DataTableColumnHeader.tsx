import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import type { Column } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function DataTableColumnHeader<TData>({
  column, title, className,
}: {
  column: Column<TData, unknown>;
  title: string;
  className?: string;
}) {
  if (!column.getCanSort()) return <div className={className}>{title}</div>;
  return (
    <Button
      variant="ghost"
      size="sm"
      className={cn("-ml-3 h-8 data-[state=open]:bg-accent", className)}
      onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
    >
      <span>{title}</span>
      {column.getIsSorted() === "asc" ? <ArrowUp className="ml-2 h-3 w-3" />
       : column.getIsSorted() === "desc" ? <ArrowDown className="ml-2 h-3 w-3" />
       : <ChevronsUpDown className="ml-2 h-3 w-3" />}
    </Button>
  );
}
