import type { ColumnDef } from "@tanstack/react-table";
import { Clock, Users, CheckCircle, ArrowLeft, GitBranch } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  listPerformance,
  getPerformance,
  listStaffConversations,
  listStaffQaReviews,
  type StaffKpiRow,
  type StaffPerformance,
  type StaffConversation,
  type StaffQaReview,
} from "../../api/adminStaffPerformance";
import { KpiCard } from "../../components/admin/KpiCard";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableColumnHeader } from "../../components/admin/data-table/DataTableColumnHeader";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "../../components/ui/breadcrumb";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { DatePicker } from "../../components/ui/date-picker";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { useStaffSession } from "../../hooks/useStaffSession";

// ── helpers ───────────────────────────────────────────────────────────────────

function toUtcParam(d: Date): string {
  return d.toISOString().slice(0, 19).replace("T", " ");
}

function fmtSeconds(s: number): string {
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}m ${sec}s`;
}

function fmtPct(r: number): string {
  return `${(r * 100).toFixed(1)}%`;
}

// ── Team overview ─────────────────────────────────────────────────────────────

function KpiSkeleton() {
  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-[100px] rounded-xl" />
      ))}
    </div>
  );
}

function buildColumns(): ColumnDef<StaffKpiRow>[] {
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
      accessorKey: "takeovers",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="接管数" />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "resolved",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="解决数" />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "transfers",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="转派数" />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "transfer_ratio",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="转派率" />
      ),
      cell: ({ row }) => fmtPct(row.original.transfer_ratio),
      enableSorting: true,
    },
    {
      accessorKey: "avg_handle_seconds",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="平均处理时长" />
      ),
      cell: ({ row }) => fmtSeconds(row.original.avg_handle_seconds),
      enableSorting: true,
    },
    {
      id: "actions",
      header: () => null,
      cell: ({ row }) => (
        <div className="flex justify-end">
          <Button variant="ghost" size="sm" asChild>
            <Link to={`/admin/performance/${row.original.staff_id}`}>
              查看详情
            </Link>
          </Button>
        </div>
      ),
    },
  ];
}

function StaffPerformanceOverview() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";

  const defaultFrom = new Date(Date.now() - 30 * 24 * 3600 * 1000);
  const defaultTo = new Date();

  const [fromDate, setFromDate] = useState<Date | undefined>(defaultFrom);
  const [toDate, setToDate] = useState<Date | undefined>(defaultTo);
  const [data, setData] = useState<{ staff: StaffKpiRow[]; team: { staff_count: number; total_takeovers: number; total_resolved: number; total_transfers: number; avg_handle_seconds: number } } | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setErr("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr("");
    const opts: { from?: string; to?: string } = {};
    if (fromDate) opts.from = toUtcParam(fromDate);
    if (toDate) opts.to = toUtcParam(toDate);
    listPerformance(token, opts)
      .then((res) => setData({ staff: res.staff, team: res.team }))
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, fromDate, toDate]);

  const columns = buildColumns();

  return (
    <PageContainer width="wide">
      <PageHeader
        title="客服绩效"
        actions={
          <div className="flex items-center gap-2">
            <DatePicker date={fromDate} onChange={setFromDate} placeholder="开始日期" />
            <span className="text-sm text-muted-foreground">至</span>
            <DatePicker date={toDate} onChange={setToDate} placeholder="结束日期" />
          </div>
        }
      />

      {err && (
        <Alert variant="error" className="mb-4">
          {err}
        </Alert>
      )}

      {loading ? (
        <KpiSkeleton />
      ) : allowed && data ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="客服人数"
            value={data.team.staff_count}
            icon={Users}
          />
          <KpiCard
            label="总接管数"
            value={data.team.total_takeovers}
            icon={CheckCircle}
          />
          <KpiCard
            label="总解决数"
            value={data.team.total_resolved}
            icon={CheckCircle}
          />
          <KpiCard
            label="团队平均处理时长"
            value={fmtSeconds(data.team.avg_handle_seconds)}
            icon={Clock}
          />
        </div>
      ) : null}

      {!loading && allowed && data && (
        <div className="mt-6">
          <DataTable
            columns={columns}
            data={data.staff}
            toolbar={(t) => (
              <DataTableToolbar
                table={t}
                searchColumn="staff_id"
                placeholder="搜索 staff_id…"
              />
            )}
          />
        </div>
      )}
    </PageContainer>
  );
}

// ── Detail ────────────────────────────────────────────────────────────────────

function DetailKpiSkeleton() {
  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-[100px] rounded-xl" />
      ))}
    </div>
  );
}

function buildConvColumns(): ColumnDef<StaffConversation>[] {
  return [
    {
      accessorKey: "id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="会话 ID" />
      ),
      cell: ({ row }) => (
        <Link
          to={`/admin/conversations/${row.original.id}`}
          className="font-mono text-xs text-primary hover:underline"
        >
          #{row.original.id}
        </Link>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "user_type",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="用户类型" />
      ),
      cell: ({ row }) => (
        <span className="font-mono text-xs">{row.original.user_type}</span>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "status",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="状态" />
      ),
      cell: ({ row }) => (
        <span className="text-xs">{row.original.status}</span>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "mode",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="模式" />
      ),
      cell: ({ row }) => (
        <span className="text-xs">{row.original.mode}</span>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "created_at",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="创建时间" />
      ),
      cell: ({ row }) => (
        <span className="text-xs">{row.original.created_at}</span>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "assigned_at",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="接管时间" />
      ),
      cell: ({ row }) => (
        <span className="text-xs">{row.original.assigned_at ?? "—"}</span>
      ),
      enableSorting: true,
    },
  ];
}

function buildQaColumns(): ColumnDef<StaffQaReview>[] {
  return [
    {
      accessorKey: "review_id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="记录 ID" />
      ),
      cell: ({ row }) => (
        <span className="font-mono text-xs">#{row.original.review_id}</span>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "conv_id",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="会话 ID" />
      ),
      cell: ({ row }) => (
        <Link
          to={`/admin/conversations/${row.original.conv_id}`}
          className="font-mono text-xs text-primary hover:underline"
        >
          #{row.original.conv_id}
        </Link>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "scorecard_name",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="评分卡" />
      ),
      cell: ({ row }) => (
        <span className="text-xs">{row.original.scorecard_name ?? "—"}</span>
      ),
      enableSorting: true,
    },
    {
      accessorKey: "total_score",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="总分" />
      ),
      enableSorting: true,
    },
    {
      accessorKey: "verdict",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="标签" />
      ),
      cell: ({ row }) => (
        <span className="text-xs">{row.original.verdict ?? "—"}</span>
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
      accessorKey: "created_at",
      header: ({ column }) => (
        <DataTableColumnHeader column={column} title="质检时间" />
      ),
      cell: ({ row }) => (
        <span className="text-xs">{row.original.created_at}</span>
      ),
      enableSorting: true,
    },
  ];
}

function OverviewTab({ p }: { p: StaffPerformance }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <Card>
          <div className="flex flex-col gap-1 p-4">
            <span className="text-xs font-medium text-muted-foreground">满意度</span>
            <div className="text-2xl font-bold">
              {p.satisfaction.avg_rating.toFixed(1)}
            </div>
            <span className="text-xs text-muted-foreground">
              共 {p.satisfaction.count} 条评价
            </span>
          </div>
        </Card>
        <Card>
          <div className="flex flex-col gap-1 p-4">
            <span className="text-xs font-medium text-muted-foreground">质检均分</span>
            <div className="text-2xl font-bold">
              {p.qa.avg_score.toFixed(1)}
            </div>
            <span className="text-xs text-muted-foreground">
              共 {p.qa.count} 次质检
            </span>
          </div>
        </Card>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <Card>
          <div className="flex flex-col gap-1 p-4">
            <span className="text-xs font-medium text-muted-foreground">解决率</span>
            <div className="text-2xl font-bold">{fmtPct(p.resolved_ratio)}</div>
          </div>
        </Card>
        <Card>
          <div className="flex flex-col gap-1 p-4">
            <span className="text-xs font-medium text-muted-foreground">转派率</span>
            <div className="text-2xl font-bold">{fmtPct(p.transfer_ratio)}</div>
          </div>
        </Card>
        <Card>
          <div className="flex flex-col gap-1 p-4">
            <span className="text-xs font-medium text-muted-foreground">释放率</span>
            <div className="text-2xl font-bold">{fmtPct(p.release_ratio)}</div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function StaffPerformanceDetail({ staffId }: { staffId: string }) {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";

  const defaultFrom = new Date(Date.now() - 30 * 24 * 3600 * 1000);
  const defaultTo = new Date();

  const [fromDate, setFromDate] = useState<Date | undefined>(defaultFrom);
  const [toDate, setToDate] = useState<Date | undefined>(defaultTo);
  const [p, setP] = useState<StaffPerformance | null>(null);
  const [convs, setConvs] = useState<StaffConversation[]>([]);
  const [qaReviews, setQaReviews] = useState<StaffQaReview[]>([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    if (!allowed) {
      setErr("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr("");
    const opts: { from?: string; to?: string } = {};
    if (fromDate) opts.from = toUtcParam(fromDate);
    if (toDate) opts.to = toUtcParam(toDate);
    Promise.all([
      getPerformance(token, staffId, opts),
      listStaffConversations(token, staffId, opts),
      listStaffQaReviews(token, staffId, opts),
    ])
      .then(([perf, convRows, qaRows]) => {
        setP(perf);
        setConvs(convRows);
        setQaReviews(qaRows);
      })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, staffId, fromDate, toDate]);

  const convColumns = buildConvColumns();
  const qaColumns = buildQaColumns();

  return (
    <PageContainer width="wide">
      {/* Breadcrumb */}
      <Breadcrumb className="mb-2">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/admin/performance">客服绩效</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{staffId}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <PageHeader
        title={`客服绩效 — ${staffId}`}
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link to="/admin/performance">
                <ArrowLeft className="mr-1 h-3.5 w-3.5" />
                返回
              </Link>
            </Button>
            <DatePicker date={fromDate} onChange={setFromDate} placeholder="开始日期" />
            <span className="text-sm text-muted-foreground">至</span>
            <DatePicker date={toDate} onChange={setToDate} placeholder="结束日期" />
          </div>
        }
      />

      {err && (
        <Alert variant="error" className="mb-4">
          {err}
        </Alert>
      )}

      {/* KPI cards */}
      {loading ? (
        <DetailKpiSkeleton />
      ) : p ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
          <KpiCard label="接管数" value={p.takeovers} icon={Users} />
          <KpiCard label="解决数" value={p.resolved} icon={CheckCircle} />
          <KpiCard label="转派数" value={p.transfers} icon={GitBranch} />
          <KpiCard
            label="平均处理时长"
            value={fmtSeconds(p.avg_handle_seconds)}
            icon={Clock}
          />
        </div>
      ) : null}

      {/* Tabs */}
      {!loading && p && (
        <Tabs defaultValue="overview" className="mt-6">
          <TabsList className="mb-3">
            <TabsTrigger value="overview">总览</TabsTrigger>
            <TabsTrigger value="conversations">会话明细</TabsTrigger>
            <TabsTrigger value="qa">质检结果</TabsTrigger>
          </TabsList>

          <TabsContent value="overview">
            <OverviewTab p={p} />
          </TabsContent>

          <TabsContent value="conversations">
            <DataTable
              columns={convColumns}
              data={convs}
              toolbar={(t) => (
                <DataTableToolbar
                  table={t}
                  searchColumn="id"
                  placeholder="搜索会话 ID…"
                />
              )}
            />
          </TabsContent>

          <TabsContent value="qa">
            <DataTable
              columns={qaColumns}
              data={qaReviews}
              toolbar={(t) => (
                <DataTableToolbar
                  table={t}
                  searchColumn="conv_id"
                  placeholder="搜索会话 ID…"
                />
              )}
            />
          </TabsContent>
        </Tabs>
      )}
    </PageContainer>
  );
}

// ── Route entry ───────────────────────────────────────────────────────────────

export function StaffPerformanceRoute() {
  const { staffId } = useParams();
  if (staffId) return <StaffPerformanceDetail staffId={staffId} />;
  return <StaffPerformanceOverview />;
}
