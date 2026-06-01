import { zodResolver } from "@hookform/resolvers/zod";
import type { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { MoreHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";

import {
  createShift,
  deleteShift,
  listShifts,
  type Shift,
} from "../../api/adminShifts";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableColumnHeader } from "../../components/admin/data-table/DataTableColumnHeader";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { DatePicker } from "../../components/ui/date-picker";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../../components/ui/dropdown-menu";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "../../components/ui/form";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "../../components/ui/sheet";
import { Skeleton } from "../../components/ui/skeleton";
import { useStaffSession } from "../../hooks/useStaffSession";

// ── Schema ──────────────────────────────────────────────────────────────────

const shiftSchema = z.object({
  staff_id: z.string().min(1, "staff_id 必填"),
  start_date: z.date(),
  start_time: z.string().regex(/^\d{2}:\d{2}$/, "格式 HH:mm"),
  end_date: z.date(),
  end_time: z.string().regex(/^\d{2}:\d{2}$/, "格式 HH:mm"),
});
type ShiftFormValues = z.infer<typeof shiftSchema>;

/** Build a UTC datetime string "YYYY-MM-DD HH:MM:SS" from date + time parts */
function buildDatetime(date: Date, time: string): string {
  return `${format(date, "yyyy-MM-dd")} ${time}:00`;
}

// ── Sheet (create only — API has no edit endpoint) ───────────────────────────

function ShiftSheet({
  open,
  onOpenChange,
  token,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  token: string;
  onSuccess: () => void;
}) {
  const form = useForm<ShiftFormValues>({
    resolver: zodResolver(shiftSchema),
    defaultValues: {
      staff_id: "",
      start_time: "09:00",
      end_time: "18:00",
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        staff_id: "",
        start_time: "09:00",
        end_time: "18:00",
        start_date: undefined,
        end_date: undefined,
      });
    }
  }, [open, form]);

  async function onSubmit(values: ShiftFormValues) {
    try {
      await createShift(token, {
        staff_id: values.staff_id,
        start_at: buildDatetime(values.start_date, values.start_time),
        end_at: buildDatetime(values.end_date, values.end_time),
      });
      toast.success("排班已创建");
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "创建失败");
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex flex-col gap-0 p-0">
        <SheetHeader className="border-b px-6 py-4">
          <SheetTitle>新建排班</SheetTitle>
        </SheetHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex flex-1 flex-col overflow-y-auto"
          >
            <div className="flex-1 space-y-5 px-6 py-5">
              <FormField
                control={form.control}
                name="staff_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Staff ID</FormLabel>
                    <FormControl>
                      <Input placeholder="staff_id" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="start_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>开始日期</FormLabel>
                    <FormControl>
                      <DatePicker
                        date={field.value}
                        onChange={field.onChange}
                        placeholder="选择开始日期"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="start_time"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>开始时间（UTC，HH:mm）</FormLabel>
                    <FormControl>
                      <Input placeholder="09:00" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="end_date"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>结束日期</FormLabel>
                    <FormControl>
                      <DatePicker
                        date={field.value}
                        onChange={field.onChange}
                        placeholder="选择结束日期"
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="end_time"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>结束时间（UTC，HH:mm）</FormLabel>
                    <FormControl>
                      <Input placeholder="18:00" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <SheetFooter className="border-t px-6 py-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
              >
                取消
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                创建
              </Button>
            </SheetFooter>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  );
}

// ── Columns ──────────────────────────────────────────────────────────────────

function buildColumns(
  token: string,
  onRefresh: () => void,
): ColumnDef<Shift>[] {
  return [
    {
      accessorKey: "id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="ID" />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "staff_id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="Staff ID" />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "start_at",
      header: "开始时间",
      cell: ({ row }) => {
        try {
          return format(new Date(row.original.start_at.replace(" ", "T") + "Z"), "yyyy-MM-dd HH:mm");
        } catch {
          return row.original.start_at;
        }
      },
      enableSorting: false,
    },
    {
      accessorKey: "end_at",
      header: "结束时间",
      cell: ({ row }) => {
        try {
          return format(new Date(row.original.end_at.replace(" ", "T") + "Z"), "yyyy-MM-dd HH:mm");
        } catch {
          return row.original.end_at;
        }
      },
      enableSorting: false,
    },
    {
      accessorKey: "created_at",
      header: "创建时间",
      cell: ({ row }) => {
        try {
          return format(new Date(row.original.created_at), "yyyy-MM-dd HH:mm");
        } catch {
          return row.original.created_at;
        }
      },
      enableSorting: false,
    },
    {
      id: "actions",
      header: () => null,
      cell: ({ row }) => {
        const s = row.original;

        async function handleDelete() {
          if (!confirm(`确认删除排班 #${s.id}（${s.staff_id}）？此操作不可撤销。`)) return;
          try {
            await deleteShift(token, s.id);
            toast.success("已删除");
            onRefresh();
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "删除失败");
          }
        }

        return (
          <div className="flex justify-end">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                  <span className="sr-only">操作</span>
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={handleDelete}
                >
                  删除
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        );
      },
    },
  ];
}

// ── Loading skeleton ─────────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-md" />
      ))}
    </div>
  );
}

// ── Route ────────────────────────────────────────────────────────────────────

export function ShiftsRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [sheetOpen, setSheetOpen] = useState(false);

  function reload() {
    if (!token) return;
    setLoading(true);
    listShifts(token)
      .then(setShifts)
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setLoadError("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  const columns = token ? buildColumns(token, reload) : [];

  return (
    <PageContainer width="wide">
      <PageHeader
        title="排班"
        actions={
          allowed && (
            <Button size="sm" onClick={() => setSheetOpen(true)}>
              新建排班
            </Button>
          )
        }
      />

      {loadError && (
        <Alert variant="destructive" className="mb-4">
          {loadError}
        </Alert>
      )}

      {loading ? (
        <SkeletonRows />
      ) : (
        <DataTable
          columns={columns}
          data={shifts}
          toolbar={(t) => (
            <DataTableToolbar
              table={t}
              searchColumn="staff_id"
              placeholder="按 staff_id 搜索…"
            />
          )}
        />
      )}

      {token && allowed && (
        <ShiftSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          token={token}
          onSuccess={reload}
        />
      )}
    </PageContainer>
  );
}
