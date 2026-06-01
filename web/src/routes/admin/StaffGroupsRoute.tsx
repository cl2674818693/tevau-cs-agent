import { zodResolver } from "@hookform/resolvers/zod";
import type { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { MoreHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";

import {
  createGroup,
  deleteGroup,
  listGroups,
  patchGroup,
  type StaffGroup,
} from "../../api/adminStaffGroups";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableColumnHeader } from "../../components/admin/data-table/DataTableColumnHeader";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
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
import { Textarea } from "../../components/ui/textarea";
import { useStaffSession } from "../../hooks/useStaffSession";

// ── Schema ──────────────────────────────────────────────────────────────────

const groupSchema = z.object({
  name: z.string().min(1, "名称必填"),
  description: z.string().optional(),
});
type GroupFormValues = z.infer<typeof groupSchema>;

// ── Sheet (create / edit) ────────────────────────────────────────────────────

function GroupSheet({
  open,
  onOpenChange,
  editing,
  token,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  editing: StaffGroup | null;
  token: string;
  onSuccess: () => void;
}) {
  const form = useForm<GroupFormValues>({
    resolver: zodResolver(groupSchema),
    defaultValues: { name: "", description: "" },
  });

  // Reset form when sheet opens / editing target changes
  useEffect(() => {
    if (open) {
      form.reset({
        name: editing?.name ?? "",
        description: editing?.description ?? "",
      });
    }
  }, [open, editing, form]);

  async function onSubmit(values: GroupFormValues) {
    try {
      if (editing) {
        await patchGroup(token, editing.id, {
          name: values.name,
          description: values.description || undefined,
        });
      } else {
        await createGroup(token, {
          name: values.name,
          description: values.description || undefined,
        });
      }
      toast.success("已保存");
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex flex-col gap-0 p-0">
        <SheetHeader className="border-b px-6 py-4">
          <SheetTitle>{editing ? "编辑分组" : "新建分组"}</SheetTitle>
        </SheetHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex flex-1 flex-col overflow-y-auto"
          >
            <div className="flex-1 space-y-5 px-6 py-5">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>名称</FormLabel>
                    <FormControl>
                      <Input placeholder="分组名称" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="description"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>描述（可选）</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="分组描述"
                        rows={3}
                        {...field}
                      />
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
                保存
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
  onEdit: (g: StaffGroup) => void,
  onRefresh: () => void,
): ColumnDef<StaffGroup>[] {
  return [
    {
      accessorKey: "name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="名称" />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "description",
      header: "描述",
      cell: ({ row }) => row.original.description ?? "-",
      enableSorting: false,
    },
    {
      accessorKey: "active",
      header: "状态",
      cell: ({ row }) =>
        row.original.active ? (
          <Badge variant="success">启用</Badge>
        ) : (
          <Badge variant="secondary">停用</Badge>
        ),
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
        const g = row.original;

        async function handleToggle() {
          try {
            await patchGroup(token, g.id, { active: g.active ? 0 : 1 });
            onRefresh();
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "操作失败");
          }
        }

        async function handleDelete() {
          if (!confirm(`确认删除分组"${g.name}"？此操作不可撤销。`)) return;
          try {
            await deleteGroup(token, g.id);
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
                <DropdownMenuItem onClick={() => onEdit(g)}>
                  编辑
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleToggle}>
                  {g.active ? "停用" : "启用"}
                </DropdownMenuItem>
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

export function StaffGroupsRoute() {
  const { token } = useStaffSession();
  const [groups, setGroups] = useState<StaffGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editing, setEditing] = useState<StaffGroup | null>(null);

  function reload() {
    if (!token) return;
    setLoading(true);
    listGroups(token)
      .then(setGroups)
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function openCreate() {
    setEditing(null);
    setSheetOpen(true);
  }

  function openEdit(g: StaffGroup) {
    setEditing(g);
    setSheetOpen(true);
  }

  const columns = token
    ? buildColumns(token, openEdit, reload)
    : [];

  return (
    <PageContainer width="wide">
      <PageHeader
        title="客服分组"
        actions={
          <Button size="sm" onClick={openCreate}>
            新建分组
          </Button>
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
          data={groups}
          toolbar={(t) => (
            <DataTableToolbar
              table={t}
              searchColumn="name"
              placeholder="搜索分组名…"
            />
          )}
        />
      )}

      {token && (
        <GroupSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          editing={editing}
          token={token}
          onSuccess={reload}
        />
      )}
    </PageContainer>
  );
}
