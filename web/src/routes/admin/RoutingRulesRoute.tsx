import { zodResolver } from "@hookform/resolvers/zod";
import type { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { MoreHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";

import {
  createRule,
  deleteRule,
  listRules,
  patchRule,
  type RoutingRule,
  setRuleActive,
} from "../../api/adminRoutingRules";
import { listGroups, type StaffGroup } from "../../api/adminStaffGroups";
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

// ── Schema ──────────────────────────────────────────────────────────────────

const MATCH_TYPES = ["user_type", "scope", "keyword"] as const;

const ruleSchema = z.object({
  match_type: z.enum(MATCH_TYPES),
  match_value: z.string().min(1, "匹配值必填"),
  target_group_id: z.number().int().min(1, "目标分组必填"),
  priority: z.number().int().min(0, "优先级须 ≥ 0"),
});
type RuleFormValues = z.infer<typeof ruleSchema>;

// ── Sheets ───────────────────────────────────────────────────────────────────

function RuleSheet({
  open,
  onOpenChange,
  token,
  groups,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  token: string;
  groups: StaffGroup[];
  onSuccess: () => void;
}) {
  const form = useForm<RuleFormValues>({
    resolver: zodResolver(ruleSchema),
    defaultValues: {
      match_type: "user_type",
      match_value: "",
      target_group_id: groups[0]?.id ?? 0,
      priority: 100,
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        match_type: "user_type",
        match_value: "",
        target_group_id: groups[0]?.id ?? 0,
        priority: 100,
      });
    }
  }, [open, groups, form]);

  async function onSubmit(values: RuleFormValues) {
    try {
      await createRule(token, {
        match_type: values.match_type,
        match_value: values.match_value,
        target_group_id: values.target_group_id,
        priority: values.priority,
      });
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
          <SheetTitle>新建规则</SheetTitle>
        </SheetHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex flex-1 flex-col overflow-y-auto"
          >
            <div className="flex-1 space-y-5 px-6 py-5">
              <FormField
                control={form.control}
                name="match_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>匹配类型</FormLabel>
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择类型" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="user_type">user_type</SelectItem>
                        <SelectItem value="scope">scope</SelectItem>
                        <SelectItem value="keyword">keyword</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="match_value"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>匹配值</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="user_type=c/b/g；keyword=文本"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="target_group_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>目标分组</FormLabel>
                    <Select
                      value={String(field.value)}
                      onValueChange={(v) => field.onChange(Number(v))}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择分组" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {groups.length === 0 ? (
                          <SelectItem value="0" disabled>
                            （先建分组）
                          </SelectItem>
                        ) : (
                          groups.map((g) => (
                            <SelectItem key={g.id} value={String(g.id)}>
                              {g.name}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="priority"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>优先级（数字越小越优先）</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={0}
                        value={field.value}
                        onChange={(e) => field.onChange(e.target.valueAsNumber)}
                        onBlur={field.onBlur}
                        name={field.name}
                        ref={field.ref}
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

function EditRuleSheet({
  rule,
  open,
  onOpenChange,
  token,
  groups,
  onSuccess,
}: {
  rule: RoutingRule;
  open: boolean;
  onOpenChange: (v: boolean) => void;
  token: string;
  groups: StaffGroup[];
  onSuccess: () => void;
}) {
  const form = useForm<RuleFormValues>({
    resolver: zodResolver(ruleSchema),
    defaultValues: {
      match_type: rule.match_type as (typeof MATCH_TYPES)[number],
      match_value: rule.match_value,
      target_group_id: rule.target_group_id,
      priority: rule.priority,
    },
  });

  useEffect(() => {
    if (open) {
      form.reset({
        match_type: rule.match_type as (typeof MATCH_TYPES)[number],
        match_value: rule.match_value,
        target_group_id: rule.target_group_id,
        priority: rule.priority,
      });
    }
  }, [open, rule, form]);

  async function onSubmit(values: RuleFormValues) {
    try {
      await patchRule(token, rule.id, {
        match_type: values.match_type,
        match_value: values.match_value,
        target_group_id: values.target_group_id,
        priority: values.priority,
      });
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
          <SheetTitle>编辑规则 #{rule.id}</SheetTitle>
        </SheetHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex flex-1 flex-col overflow-y-auto"
          >
            <div className="flex-1 space-y-5 px-6 py-5">
              <FormField
                control={form.control}
                name="match_type"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>匹配类型</FormLabel>
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择类型" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="user_type">user_type</SelectItem>
                        <SelectItem value="scope">scope</SelectItem>
                        <SelectItem value="keyword">keyword</SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="match_value"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>匹配值</FormLabel>
                    <FormControl>
                      <Input
                        placeholder="user_type=c/b/g；keyword=文本"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="target_group_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>目标分组</FormLabel>
                    <Select
                      value={String(field.value)}
                      onValueChange={(v) => field.onChange(Number(v))}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择分组" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {groups.length === 0 ? (
                          <SelectItem value="0" disabled>
                            （先建分组）
                          </SelectItem>
                        ) : (
                          groups.map((g) => (
                            <SelectItem key={g.id} value={String(g.id)}>
                              {g.name}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="priority"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>优先级（数字越小越优先）</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={0}
                        value={field.value}
                        onChange={(e) => field.onChange(e.target.valueAsNumber)}
                        onBlur={field.onBlur}
                        name={field.name}
                        ref={field.ref}
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
  groupName: (id: number) => string,
  onRefresh: () => void,
  onEdit: (r: RoutingRule) => void,
): ColumnDef<RoutingRule>[] {
  return [
    {
      accessorKey: "priority",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="优先级" />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "match_type",
      header: "类型",
      enableSorting: false,
    },
    {
      accessorKey: "match_value",
      header: "匹配值",
      enableSorting: false,
    },
    {
      id: "target_group",
      header: "目标分组",
      cell: ({ row }) => groupName(row.original.target_group_id),
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
        const r = row.original;

        async function handleToggle() {
          try {
            await setRuleActive(token, r.id, r.active ? 0 : 1);
            toast.success(r.active ? "已停用" : "已启用");
            onRefresh();
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "操作失败");
          }
        }

        async function handleDelete() {
          if (
            !confirm(
              `确认删除规则（${r.match_type}=${r.match_value}）？此操作不可撤销。`,
            )
          )
            return;
          try {
            await deleteRule(token, r.id);
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
                <DropdownMenuItem onClick={() => onEdit(r)}>
                  编辑
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleToggle}>
                  {r.active ? "停用" : "启用"}
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

export function RoutingRulesRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";

  const [rules, setRules] = useState<RoutingRule[]>([]);
  const [groups, setGroups] = useState<StaffGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editRule, setEditRule] = useState<RoutingRule | null>(null);

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([listRules(token), listGroups(token)])
      .then(([rs, gs]) => {
        setRules(rs);
        setGroups(gs);
      })
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setLoadError("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  const groupName = (id: number) =>
    groups.find((g) => g.id === id)?.name ?? `#${id}`;

  const columns =
    token && allowed ? buildColumns(token, groupName, reload, setEditRule) : [];

  return (
    <PageContainer width="wide">
      <PageHeader
        title="会话路由"
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
              searchColumn="match_value"
              placeholder="搜索匹配值…"
            />
          )}
        />
      )}

      {token && allowed && (
        <RuleSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          token={token}
          groups={groups}
          onSuccess={reload}
        />
      )}

      {token && allowed && editRule && (
        <EditRuleSheet
          rule={editRule}
          open={!!editRule}
          onOpenChange={(v) => { if (!v) setEditRule(null); }}
          token={token}
          groups={groups}
          onSuccess={reload}
        />
      )}
    </PageContainer>
  );
}
