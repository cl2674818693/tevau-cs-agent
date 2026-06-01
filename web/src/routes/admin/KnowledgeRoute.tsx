import { zodResolver } from "@hookform/resolvers/zod";
import type { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { MoreHorizontal } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import * as z from "zod";

import {
  createKnowledge,
  deleteKnowledge,
  type KnowledgeEntry,
  listKnowledge,
  publishKnowledge,
} from "../../api/adminKnowledge";
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

// ── Constants ────────────────────────────────────────────────────────────────

const TYPES = ["faq", "api_doc", "error_code"] as const;

// ── Schema ───────────────────────────────────────────────────────────────────

const knowledgeSchema = z.object({
  type: z.string().min(1, "类型必填"),
  key: z.string().min(1, "Key 必填"),
  title: z.string().min(1, "标题必填"),
  content: z.string().optional(),
  locale: z.string().optional(),
});
type KnowledgeFormValues = z.infer<typeof knowledgeSchema>;

// ── Sheet (create) ────────────────────────────────────────────────────────────

function KnowledgeSheet({
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
  const form = useForm<KnowledgeFormValues>({
    resolver: zodResolver(knowledgeSchema),
    defaultValues: { type: "faq", key: "", title: "", content: "", locale: "" },
  });

  useEffect(() => {
    if (open) {
      form.reset({ type: "faq", key: "", title: "", content: "", locale: "" });
    }
  }, [open, form]);

  async function onSubmit(values: KnowledgeFormValues) {
    try {
      await createKnowledge(token, {
        type: values.type,
        key: values.key,
        title: values.title,
        content: values.content ?? "",
        locale: values.locale || undefined,
      });
      toast.success("已创建草稿");
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
          <SheetTitle>新建知识条目</SheetTitle>
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
                    <FormControl>
                      <select
                        {...field}
                        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      >
                        {TYPES.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="key"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Key</FormLabel>
                    <FormControl>
                      <Input placeholder="错误码 / 路径 / slug" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>标题</FormLabel>
                    <FormControl>
                      <Input placeholder="条目标题" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="locale"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>语言（可选）</FormLabel>
                    <FormControl>
                      <Input placeholder="zh / en / …" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="content"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>内容（Markdown）</FormLabel>
                    <FormControl>
                      <Textarea
                        placeholder="Markdown 内容"
                        rows={8}
                        className="font-mono text-sm"
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
                创建草稿
              </Button>
            </SheetFooter>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  );
}

// ── Columns ───────────────────────────────────────────────────────────────────

function buildColumns(
  token: string,
  onRefresh: () => void,
): ColumnDef<KnowledgeEntry>[] {
  return [
    {
      accessorKey: "type",
      header: "类型",
      cell: ({ row }) => (
        <Badge variant="neutral" className="font-mono text-xs">
          {row.original.type}
        </Badge>
      ),
      enableSorting: false,
    },
    {
      accessorKey: "key",
      header: "Key",
      cell: ({ row }) => (
        <span className="font-mono text-sm">{row.original.key}</span>
      ),
      enableSorting: false,
    },
    {
      accessorKey: "title",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="标题" />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "status",
      header: "状态",
      cell: ({ row }) => {
        const s = row.original.status;
        return s === "published" ? (
          <Badge variant="success">已发布</Badge>
        ) : (
          <Badge variant="neutral">草稿</Badge>
        );
      },
      enableSorting: false,
    },
    {
      accessorKey: "source_gap_signal",
      header: "来源",
      cell: ({ row }) => row.original.source_gap_signal ?? "—",
      enableSorting: false,
    },
    {
      accessorKey: "updated_at",
      header: "更新时间",
      cell: ({ row }) => {
        try {
          return format(new Date(row.original.updated_at), "yyyy-MM-dd HH:mm");
        } catch {
          return row.original.updated_at;
        }
      },
      enableSorting: false,
    },
    {
      id: "actions",
      header: () => null,
      cell: ({ row }) => {
        const e = row.original;

        async function handlePublish() {
          try {
            await publishKnowledge(token, e.id);
            toast.success("已发布");
            onRefresh();
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "发布失败");
          }
        }

        async function handleDelete() {
          if (!confirm(`确认删除"${e.title}"？此操作不可撤销。`)) return;
          try {
            await deleteKnowledge(token, e.id);
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
                {e.status === "draft" && (
                  <DropdownMenuItem onClick={handlePublish}>
                    发布
                  </DropdownMenuItem>
                )}
                {e.status === "draft" && <DropdownMenuSeparator />}
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

export function KnowledgeRoute() {
  const { token, role } = useStaffSession();
  const allowed =
    role === "supervisor" || role === "engineer" || role === "admin";

  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [sheetOpen, setSheetOpen] = useState(false);

  function reload() {
    if (!token) return;
    setLoading(true);
    listKnowledge(token)
      .then(setEntries)
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载失败"),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setLoadError("需要主管 / 工程师 / 管理员权限");
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
        title="知识库"
        actions={
          allowed && (
            <Button size="sm" onClick={() => setSheetOpen(true)}>
              新建条目
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
          data={entries}
          toolbar={(t) => (
            <DataTableToolbar
              table={t}
              searchColumn="title"
              placeholder="搜索标题…"
            />
          )}
        />
      )}

      {token && allowed && (
        <KnowledgeSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          token={token}
          onSuccess={reload}
        />
      )}
    </PageContainer>
  );
}
