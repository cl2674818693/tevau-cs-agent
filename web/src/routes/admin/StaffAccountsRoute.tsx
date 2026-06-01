import { zodResolver } from "@hookform/resolvers/zod";
import type { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { MoreHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";

import {
  createStaff,
  listStaff,
  patchStaff,
  resetPassword,
  STAFF_ROLES,
  type StaffRow,
} from "../../api/adminStaff";
import { listGroups, type StaffGroup } from "../../api/adminStaffGroups";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableColumnHeader } from "../../components/admin/data-table/DataTableColumnHeader";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
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
import { Switch } from "../../components/ui/switch";
import { useStaffSession } from "../../hooks/useStaffSession";

// ── Role label map ────────────────────────────────────────────────────────────

const ROLE_LABEL: Record<string, string> = {
  agent: "客服",
  senior: "高级",
  supervisor: "主管",
  engineer: "工程",
  manager: "经理",
  admin: "管理员",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function parseSkills(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) return parsed.filter((s) => typeof s === "string");
    return [];
  } catch {
    return [];
  }
}

function formatDate(val: string) {
  try {
    return format(new Date(val), "yyyy-MM-dd HH:mm");
  } catch {
    return val;
  }
}

// ── Schemas ───────────────────────────────────────────────────────────────────

const createSchema = z.object({
  staff_id: z
    .string()
    .min(1, "staff_id 必填")
    .regex(/^[a-z][a-z0-9_]*$/, "小写字母+数字+下划线"),
  display_name: z.string().min(1, "显示名必填"),
  role: z.enum(["agent", "senior", "supervisor", "engineer", "manager", "admin"]),
  password: z.string().min(8, "密码至少 8 位"),
});
type CreateFormValues = z.infer<typeof createSchema>;

const editSchema = z.object({
  display_name: z.string().min(1, "显示名必填"),
  role: z.enum(["agent", "senior", "supervisor", "engineer", "manager", "admin"]),
  group_id: z.string(), // "__none__" | stringified number
  skills: z.string(), // comma-separated
  active: z.boolean(),
});
type EditFormValues = z.infer<typeof editSchema>;

const resetPwSchema = z.object({
  password: z.string().min(8, "密码至少 8 位"),
});
type ResetPwFormValues = z.infer<typeof resetPwSchema>;

// ── Create Sheet ──────────────────────────────────────────────────────────────

function CreateSheet({
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
  const form = useForm<CreateFormValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { staff_id: "", display_name: "", role: "agent", password: "" },
  });

  useEffect(() => {
    if (open) form.reset({ staff_id: "", display_name: "", role: "agent", password: "" });
  }, [open, form]);

  async function onSubmit(values: CreateFormValues) {
    try {
      await createStaff(token, values);
      toast.success("已创建");
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
          <SheetTitle>新建客服</SheetTitle>
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
                    <FormLabel>staff_id</FormLabel>
                    <FormControl>
                      <Input placeholder="小写字母开头" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="display_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>显示名</FormLabel>
                    <FormControl>
                      <Input placeholder="显示名" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="role"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>角色</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择角色" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {STAFF_ROLES.map((r) => (
                          <SelectItem key={r} value={r}>
                            {ROLE_LABEL[r] ?? r}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>初始密码</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="至少 8 位" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <SheetFooter className="border-t px-6 py-4">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
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

// ── Edit Sheet ────────────────────────────────────────────────────────────────

function EditSheet({
  open,
  onOpenChange,
  staff,
  groups,
  token,
  onSuccess,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  staff: StaffRow | null;
  groups: StaffGroup[];
  token: string;
  onSuccess: () => void;
}) {
  const form = useForm<EditFormValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      display_name: "",
      role: "agent",
      group_id: "__none__",
      skills: "",
      active: true,
    },
  });

  useEffect(() => {
    if (open && staff) {
      form.reset({
        display_name: staff.display_name,
        role: staff.role as EditFormValues["role"],
        group_id: staff.group_id != null ? String(staff.group_id) : "__none__",
        skills: parseSkills(staff.skills).join(", "),
        active: staff.active === 1,
      });
    }
  }, [open, staff, form]);

  async function onSubmit(values: EditFormValues) {
    if (!staff) return;
    try {
      const skillsArr = values.skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const groupId = values.group_id === "__none__" ? null : Number(values.group_id);

      await patchStaff(token, staff.staff_id, {
        display_name: values.display_name,
        role: values.role,
        group_id: groupId,
        skills: skillsArr,
        active: values.active ? 1 : 0,
      });
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
          <SheetTitle>编辑客服 {staff?.staff_id}</SheetTitle>
        </SheetHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex flex-1 flex-col overflow-y-auto"
          >
            <div className="flex-1 space-y-5 px-6 py-5">
              <FormField
                control={form.control}
                name="display_name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>显示名</FormLabel>
                    <FormControl>
                      <Input placeholder="显示名" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="role"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>角色</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择角色" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {STAFF_ROLES.map((r) => (
                          <SelectItem key={r} value={r}>
                            {ROLE_LABEL[r] ?? r}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="group_id"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>分组</FormLabel>
                    <Select onValueChange={field.onChange} value={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="选择分组" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="__none__">无</SelectItem>
                        {groups.map((g) => (
                          <SelectItem key={g.id} value={String(g.id)}>
                            {g.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="skills"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>技能（逗号分隔）</FormLabel>
                    <FormControl>
                      <Input placeholder="如: 英语, 理财" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="active"
                render={({ field }) => (
                  <FormItem className="flex items-center gap-3">
                    <FormLabel className="mt-0">启用</FormLabel>
                    <FormControl>
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <SheetFooter className="border-t px-6 py-4">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
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

// ── Reset Password Dialog ─────────────────────────────────────────────────────

function ResetPasswordDialog({
  open,
  onOpenChange,
  staffId,
  token,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  staffId: string | null;
  token: string;
}) {
  const form = useForm<ResetPwFormValues>({
    resolver: zodResolver(resetPwSchema),
    defaultValues: { password: "" },
  });

  useEffect(() => {
    if (open) form.reset({ password: "" });
  }, [open, form]);

  async function onSubmit(values: ResetPwFormValues) {
    if (!staffId) return;
    try {
      await resetPassword(token, staffId, values.password);
      toast.success("密码已重置");
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "重置失败");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>重置密码 — {staffId}</DialogTitle>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>新密码</FormLabel>
                  <FormControl>
                    <Input type="password" placeholder="至少 8 位" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                取消
              </Button>
              <Button type="submit" disabled={form.formState.isSubmitting}>
                确认重置
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}

// ── Columns ───────────────────────────────────────────────────────────────────

function buildColumns(
  token: string,
  groups: StaffGroup[],
  onEdit: (s: StaffRow) => void,
  onResetPw: (staffId: string) => void,
  onRefresh: () => void,
): ColumnDef<StaffRow>[] {
  const groupMap = new Map(groups.map((g) => [g.id, g.name]));

  return [
    {
      accessorKey: "staff_id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="staff_id" />
      ),
      cell: ({ row }) => (
        <span className="font-mono text-xs">{row.original.staff_id}</span>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "display_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="显示名" />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "role",
      header: "角色",
      cell: ({ row }) => {
        const role = row.original.role;
        return <Badge variant="outline">{ROLE_LABEL[role] ?? role}</Badge>;
      },
      enableSorting: false,
    },
    {
      accessorKey: "group_id",
      header: "分组",
      cell: ({ row }) => {
        const gid = row.original.group_id;
        if (gid == null) return <span className="text-muted-foreground">-</span>;
        return groupMap.get(gid) ?? <span className="text-muted-foreground">-</span>;
      },
      enableSorting: false,
    },
    {
      accessorKey: "skills",
      header: "技能",
      cell: ({ row }) => {
        const skills = parseSkills(row.original.skills);
        if (!skills.length) return <span className="text-muted-foreground">-</span>;
        return (
          <div className="flex flex-wrap gap-1">
            {skills.map((sk) => (
              <Badge key={sk} variant="secondary" className="text-xs">
                {sk}
              </Badge>
            ))}
          </div>
        );
      },
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
      cell: ({ row }) => formatDate(row.original.created_at),
      enableSorting: false,
    },
    {
      id: "actions",
      header: () => null,
      cell: ({ row }) => {
        const s = row.original;

        async function handleToggleActive() {
          try {
            await patchStaff(token, s.staff_id, { active: s.active === 1 ? 0 : 1 });
            onRefresh();
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "操作失败");
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
                <DropdownMenuItem onClick={() => onEdit(s)}>编辑</DropdownMenuItem>
                <DropdownMenuItem onClick={() => onResetPw(s.staff_id)}>
                  重置密码
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleToggleActive}>
                  {s.active ? "停用" : "启用"}
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
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-md" />
      ))}
    </div>
  );
}

// ── Route ─────────────────────────────────────────────────────────────────────

export function StaffAccountsRoute() {
  const { token } = useStaffSession();
  const [rows, setRows] = useState<StaffRow[]>([]);
  const [groups, setGroups] = useState<StaffGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<StaffRow | null>(null);
  const [resetPwOpen, setResetPwOpen] = useState(false);
  const [resetPwTarget, setResetPwTarget] = useState<string | null>(null);

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([listStaff(token), listGroups(token)])
      .then(([rs, gs]) => {
        setRows(rs);
        setGroups(gs);
      })
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function openEdit(s: StaffRow) {
    setEditTarget(s);
    setEditOpen(true);
  }

  function openResetPw(staffId: string) {
    setResetPwTarget(staffId);
    setResetPwOpen(true);
  }

  const columns =
    token ? buildColumns(token, groups, openEdit, openResetPw, reload) : [];

  return (
    <PageContainer width="wide">
      <PageHeader
        title="客服账号"
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            新建客服
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
          data={rows}
          toolbar={(t) => (
            <DataTableToolbar
              table={t}
              searchColumn="staff_id"
              placeholder="搜索 staff_id…"
            />
          )}
        />
      )}

      {token && (
        <>
          <CreateSheet
            open={createOpen}
            onOpenChange={setCreateOpen}
            token={token}
            onSuccess={reload}
          />
          <EditSheet
            open={editOpen}
            onOpenChange={setEditOpen}
            staff={editTarget}
            groups={groups}
            token={token}
            onSuccess={reload}
          />
          <ResetPasswordDialog
            open={resetPwOpen}
            onOpenChange={setResetPwOpen}
            staffId={resetPwTarget}
            token={token}
          />
        </>
      )}
    </PageContainer>
  );
}
