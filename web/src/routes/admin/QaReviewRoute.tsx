import type { ColumnDef } from "@tanstack/react-table";
import { format } from "date-fns";
import { ExternalLink, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import {
  listReviews,
  listScorecards,
  submitReview,
  type QaReview,
  type Scorecard,
} from "../../api/adminQa";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableColumnHeader } from "../../components/admin/data-table/DataTableColumnHeader";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { DatePicker } from "../../components/ui/date-picker";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
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

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDateTime(val: string) {
  try {
    return format(new Date(val), "yyyy-MM-dd HH:mm:ss");
  } catch {
    return val;
  }
}

function ScoreBadge({ score }: { score: number }) {
  const variant =
    score >= 90 ? "default" : score >= 70 ? "secondary" : "destructive";
  return <Badge variant={variant}>{score}</Badge>;
}

// ── Loading skeleton ──────────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 8 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-md" />
      ))}
    </div>
  );
}

// ── Submit Review Sheet ───────────────────────────────────────────────────────

interface ReviewSheetProps {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  scorecards: Scorecard[];
  defaultConvId?: number;
  token: string;
  onSuccess: () => void;
}

function ReviewSheet({
  open,
  onOpenChange,
  scorecards,
  defaultConvId,
  token,
  onSuccess,
}: ReviewSheetProps) {
  const [convId, setConvId] = useState(defaultConvId ?? 0);
  const [scid, setScid] = useState(scorecards[0]?.id ?? 0);
  const [score, setScore] = useState(80);
  const [tags, setTags] = useState("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setConvId(defaultConvId ?? 0);
      setScid(scorecards[0]?.id ?? 0);
      setScore(80);
      setTags("");
      setComment("");
    }
  }, [open, defaultConvId, scorecards]);

  async function handleSubmit() {
    if (!scid || !convId) {
      toast.error("请填写会话 ID 并选择评分卡");
      return;
    }
    setSubmitting(true);
    try {
      await submitReview(token, {
        conversation_id: convId,
        scorecard_id: scid,
        score,
        items_result: {},
        tags: tags || undefined,
        comment: comment || undefined,
      });
      toast.success("质检已提交");
      onOpenChange(false);
      onSuccess();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex flex-col gap-0 p-0">
        <SheetHeader className="border-b px-6 py-4">
          <SheetTitle>提交质检</SheetTitle>
        </SheetHeader>

        <div className="flex flex-1 flex-col gap-5 overflow-y-auto px-6 py-5">
          {/* 会话 ID */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="qa-conv-id">会话 ID</Label>
            <Input
              id="qa-conv-id"
              type="number"
              min={1}
              value={convId || ""}
              placeholder="输入会话 ID"
              onChange={(e) => setConvId(Number(e.target.value))}
            />
          </div>

          {/* 评分卡 */}
          <div className="flex flex-col gap-1.5">
            <Label>评分卡</Label>
            <Select
              value={String(scid)}
              onValueChange={(v) => setScid(Number(v))}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择评分卡" />
              </SelectTrigger>
              <SelectContent>
                {scorecards.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 得分 */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="qa-score">得分（0–100）</Label>
            <Input
              id="qa-score"
              type="number"
              min={0}
              max={100}
              value={score}
              onChange={(e) => setScore(Number(e.target.value))}
            />
          </div>

          {/* 标签 */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="qa-tags">标签</Label>
            <Input
              id="qa-tags"
              placeholder="excellent / violation / …"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
            />
          </div>

          {/* 备注 */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="qa-comment">备注</Label>
            <textarea
              id="qa-comment"
              className="min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
              placeholder="可选备注"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>
        </div>

        <SheetFooter className="border-t px-6 py-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            取消
          </Button>
          <Button
            type="button"
            disabled={submitting || !scid || !convId}
            onClick={handleSubmit}
          >
            {submitting ? "提交中…" : "提交质检"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

// ── Columns ───────────────────────────────────────────────────────────────────

function buildColumns(
  onReview: (row: QaReview) => void,
): ColumnDef<QaReview>[] {
  return [
    {
      accessorKey: "created_at",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="时间" />
      ),
      cell: ({ row }) => (
        <span className="whitespace-nowrap font-mono text-xs text-muted-foreground">
          {formatDateTime(row.original.created_at)}
        </span>
      ),
      enableSorting: true,
      sortDescFirst: true,
    },
    {
      accessorKey: "conversation_id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="会话" />
      ),
      cell: ({ row }) => (
        <span className="font-mono text-xs text-foreground">
          #{row.original.conversation_id}
        </span>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "reviewer_staff_id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="质检员" />
      ),
      cell: ({ row }) => (
        <span className="font-mono text-xs">{row.original.reviewer_staff_id}</span>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "score",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="得分" />
      ),
      cell: ({ row }) => <ScoreBadge score={row.original.score} />,
      enableSorting: true,
    },
    {
      accessorKey: "tags",
      header: "标签",
      cell: ({ row }) =>
        row.original.tags ? (
          <span className="text-xs text-muted-foreground">{row.original.tags}</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
      enableSorting: false,
    },
    {
      accessorKey: "comment",
      header: "备注",
      cell: ({ row }) =>
        row.original.comment ? (
          <span className="text-xs text-muted-foreground">{row.original.comment}</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
      enableSorting: false,
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => {
        const convId = row.original.conversation_id;
        return (
          <div className="flex items-center gap-2">
            <Link
              to={`/staff/conversations/${convId}/logs`}
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              <ExternalLink className="h-3 w-3" />
              查看
            </Link>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 px-2 text-xs"
              onClick={() => onReview(row.original)}
            >
              重新质检
            </Button>
          </div>
        );
      },
      enableSorting: false,
    },
  ];
}

// ── Filter state ──────────────────────────────────────────────────────────────

interface FilterState {
  dateFrom: Date | undefined;
  dateTo: Date | undefined;
}

// ── Route ─────────────────────────────────────────────────────────────────────

export function QaReviewRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";

  const [reviews, setReviews] = useState<QaReview[]>([]);
  const [scorecards, setScorecards] = useState<Scorecard[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [filter, setFilter] = useState<FilterState>({
    dateFrom: undefined,
    dateTo: undefined,
  });
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetConvId, setSheetConvId] = useState<number | undefined>(undefined);

  function reload(f: FilterState = filter) {
    if (!token) return;
    setLoading(true);
    setErr("");
    Promise.all([listScorecards(token, true), listReviews(token)])
      .then(([sc, rv]) => {
        setScorecards(sc);
        // Client-side date filter
        const from = f.dateFrom ? f.dateFrom.getTime() : null;
        const to = f.dateTo
          ? new Date(
              f.dateTo.getFullYear(),
              f.dateTo.getMonth(),
              f.dateTo.getDate(),
              23,
              59,
              59,
              999,
            ).getTime()
          : null;
        const filtered =
          from != null || to != null
            ? rv.filter((r) => {
                const t = new Date(r.created_at).getTime();
                if (from != null && t < from) return false;
                if (to != null && t > to) return false;
                return true;
              })
            : rv;
        const sorted = [...filtered].sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        );
        setReviews(sorted);
      })
      .catch(() => setErr("加载失败，请重试"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setErr("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  function openReviewSheet(row?: QaReview) {
    setSheetConvId(row?.conversation_id);
    setSheetOpen(true);
  }

  const columns = buildColumns((row) => openReviewSheet(row));

  return (
    <PageContainer width="wide">
      <PageHeader
        title="会话质检"
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => reload()}
              disabled={loading}
            >
              <RefreshCw
                className={`mr-1.5 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
              />
              刷新
            </Button>
            {allowed && (
              <Button size="sm" onClick={() => openReviewSheet()}>
                新建质检
              </Button>
            )}
          </div>
        }
      />

      {err && (
        <Alert variant="destructive" className="mb-4">
          {err}
        </Alert>
      )}

      {allowed && (
        <>
          {/* Date range filter */}
          <div className="mb-3 flex flex-wrap items-end gap-2">
            <DatePicker
              date={filter.dateFrom}
              onChange={(d) => setFilter((f) => ({ ...f, dateFrom: d }))}
              placeholder="开始日期"
            />
            <DatePicker
              date={filter.dateTo}
              onChange={(d) => setFilter((f) => ({ ...f, dateTo: d }))}
              placeholder="结束日期"
            />
            <Button
              variant="default"
              size="sm"
              onClick={() => reload(filter)}
              disabled={loading}
            >
              筛选
            </Button>
            {(filter.dateFrom || filter.dateTo) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  const next = { ...filter, dateFrom: undefined, dateTo: undefined };
                  setFilter(next);
                  reload(next);
                }}
              >
                清除日期
              </Button>
            )}
          </div>

          {loading ? (
            <SkeletonRows />
          ) : (
            <DataTable
              columns={columns}
              data={reviews}
              toolbar={(t) => (
                <DataTableToolbar
                  table={t}
                  searchColumn="conversation_id"
                  placeholder="搜索会话 ID…"
                />
              )}
              empty="暂无质检记录"
            />
          )}
        </>
      )}

      {token && (
        <ReviewSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          scorecards={scorecards}
          defaultConvId={sheetConvId}
          token={token}
          onSuccess={() => reload()}
        />
      )}
    </PageContainer>
  );
}
