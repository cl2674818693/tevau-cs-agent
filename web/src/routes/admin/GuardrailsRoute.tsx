import { zodResolver } from "@hookform/resolvers/zod";
import type { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { MoreHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";

import {
  createGuardrail,
  deleteGuardrail,
  type Guardrail,
  listGuardrails,
  patchGuardrail,
  setGuardrailActive,
} from "../../api/adminGuardrails";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "../../components/ui/sheet";
import { Skeleton } from "../../components/ui/skeleton";
import { useStaffSession } from "../../hooks/useStaffSession";

// ── Schema ───────────────────────────────────────────────────────────────────

const GUARDRAIL_TYPES = ["blocklist", "sensitive_word", "scope_toggle"] as const;
const GUARDRAIL_ACTIONS = ["block", "flag"] as const;

const guardrailSchema = z.object({
  type: z.enum(GUARDRAIL_TYPES),
  pattern: z.string().min(1, "pattern 必填"),
  action: z.enum(GUARDRAIL_ACTIONS),
});
type GuardrailFormValues = z.infer<typeof guardrailSchema>;

// ── Sheets ───────────────────────────────────────────────────────────────────

function GuardrailSheet({
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
  const form = useForm<GuardrailFormValues>({
    resolver: zodResolver(guardrailSchema),
    defaultValues: {
      type: "sensitive_word",
      pattern: "",
      action: "block",
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({ type: "sensitive_word", pattern: "", action: "block" });
    }
  }, [open, form]);

  async function onSubmit(values: GuardrailFormValues) {
    try {
      await createGuardrail(token, values);
      toast.success("规则已创建");
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
          <SheetTitle>新建拦截规则</SheetTitle>
        </SheetHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex flex-1 flex-col overflow-y-auto"
          >
            <div className="flex-1 space-y-5 px-6 py-5">
              <FormField
                control={form.control}
                name="type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>类型</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择类型" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="blocklist">blocklist</SelectItem>
                        <SelectItem value="sensitive_word">sensitive_word</SelectItem>
                        <SelectItem value="scope_toggle">scope_toggle</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="pattern"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>pattern</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="subject_id / 词 / scope 名"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="action"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>动作</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择动作" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="block">block</SelectItem>
                        <SelectItem value="flag">flag</SelectItem>
                      </SelectContent>
                    </Select>
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

// ── Edit Sheet ───────────────────────────────────────────────────────────────

function EditGuardrailSheet({
  guardrail,
  open,
  onOpenChange,
  token,
  onSuccess,
}: {
  guardrail: Guardrail;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  token: string;
  onSuccess: () => void;
}) {
  const form = useForm<GuardrailFormValues>({
    resolver: zodResolver(guardrailSchema),
    defaultValues: {
      type: guardrail.type as (typeof GUARDRAIL_TYPES)[number],
      pattern: guardrail.pattern,
      action: guardrail.action as (typeof GUARDRAIL_ACTIONS)[number],
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        type: guardrail.type as (typeof GUARDRAIL_TYPES)[number],
        pattern: guardrail.pattern,
        action: guardrail.action as (typeof GUARDRAIL_ACTIONS)[number],
      });
    }
  }, [open, guardrail, form]);

  async function onSubmit(values: GuardrailFormValues) {
    try {
      await patchGuardrail(token, guardrail.id, values);
      toast.success("规则已更新");
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "更新失败");
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex flex-col gap-0 p-0">
        <SheetHeader className="border-b px-6 py-4">
          <SheetTitle>编辑规则 #{guardrail.id}</SheetTitle>
        </SheetHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex flex-1 flex-col overflow-y-auto"
          >
            <div className="flex-1 space-y-5 px-6 py-5">
              <FormField
                control={form.control}
                name="type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>类型</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择类型" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="blocklist">blocklist</SelectItem>
                        <SelectItem value="sensitive_word">sensitive_word</SelectItem>
                        <SelectItem value="scope_toggle">scope_toggle</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="pattern"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>pattern</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="subject_id / 词 / scope 名"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="action"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>动作</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择动作" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="block">block</SelectItem>
                        <SelectItem value="flag">flag</SelectItem>
                      </SelectContent>
                    </Select>
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
  onRefresh: () => void,
  onEdit: (g: Guardrail) => void,
): ColumnDef<Guardrail>[] {
  return [
    {
      accessorKey: "id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="ID" />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "type",
      header: "类型",
      enableSorting: false,
    },
    {
      accessorKey: "pattern",
      header: "pattern",
      enableSorting: false,
    },
    {
      accessorKey: "action",
      header: "动作",
      enableSorting: false,
    },
    {
      accessorKey: "active",
      header: "状态",
      cell: ({ row }) =>
        row.original.active ? (
          <Badge variant="success">启用</Badge>
        ) : (
          <Badge variant="neutral">停用</Badge>
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
            await setGuardrailActive(token, g.id, g.active ? 0 : 1);
            toast.success(g.active ? "已停用" : "已启用");
            onRefresh();
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "操作失败");
          }
        }

        async function handleDelete() {
          if (!confirm(`确认删除规则（${g.type}=${g.pattern}）？此操作不可撤销。`))
            return;
          try {
            await deleteGuardrail(token, g.id);
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

// ── Loading skeleton ──────────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-md" />
      ))}
    </div>
  );
}

// ── Route ─────────────────────────────────────────────────────────────────────

export function GuardrailsRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";

  const [rules, setRules] = useState<Guardrail[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editGuardrail, setEditGuardrail] = useState<Guardrail | null>(null);

  function reload() {
    if (!token) return;
    setLoading(true);
    listGuardrails(token)
      .then(setRules)
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setLoadError("需要工程或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  const columns = token && allowed ? buildColumns(token, reload, setEditGuardrail) : [];

  return (
    <PageContainer width="wide">
      <PageHeader
        title="范围拦截"
        actions={
          allowed && (
            <Button size="sm" onClick={() => setSheetOpen(true)}>
              新建规则
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
          data={rules}
          toolbar={(t) => (
            <DataTableToolbar
              table={t}
              searchColumn="pattern"
              placeholder="搜索 pattern…"
            />
          )}
        />
      )}

      {token && allowed && (
        <GuardrailSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          token={token}
          onSuccess={reload}
        />
      )}

      {token && allowed && editGuardrail && (
        <EditGuardrailSheet
          guardrail={editGuardrail}
          open={!!editGuardrail}
          onOpenChange={(v) => { if (!v) setEditGuardrail(null); }}
          token={token}
          onSuccess={reload}
        />
      )}
    </PageContainer>
  );
}
