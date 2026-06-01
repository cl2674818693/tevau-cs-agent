import type { ColumnDef } from "@tanstack/react-table";
import { Clock, Users, CheckCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  listPerformance,
  getPerformance,
  type StaffKpiRow,
  type StaffPerformance,
} from "../../api/adminStaffPerformance";
import { KpiCard } from "../../components/admin/KpiCard";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableColumnHeader } from "../../components/admin/data-table/DataTableColumnHeader";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { DatePicker } from "../../components/ui/date-picker";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { LoadingState } from "../../components/ui/spinner";
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

// ── Detail (Phase 3 placeholder / existing logic) ─────────────────────────────

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <Card>
      <div className="flex flex-col gap-1 px-page py-block">
        <span className="text-footnote text-ink-secondary">{label}</span>
        <span className="text-h3 text-ink-primary">{value}</span>
      </div>
    </Card>
  );
}

function StatsGrid({ p }: { p: StaffPerformance }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
      <Stat label="接管数" value={p.takeovers} />
      <Stat label="解决数" value={p.resolved} />
      <Stat label="转派数" value={p.transfers} />
      <Stat label="平均处理(秒)" value={Math.round(p.avg_handle_seconds)} />
      <Stat
        label="满意度(均/数)"
        value={`${p.satisfaction.avg_rating.toFixed(1)} / ${p.satisfaction.count}`}
      />
      <Stat
        label="质检均分(分/数)"
        value={`${p.qa.avg_score.toFixed(1)} / ${p.qa.count}`}
      />
    </div>
  );
}

function StaffPerformanceDetail({ staffId }: { staffId: string }) {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [queryId, setQueryId] = useState(staffId);
  const [p, setP] = useState<StaffPerformance | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token || !allowed) {
      setErr("需要主管或管理员权限");
      return;
    }
    if (!queryId) return;
    setLoading(true);
    setErr("");
    getPerformance(token, queryId)
      .then(setP)
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, queryId]);

  return (
    <PageContainer width="wide">
      <PageHeader title="客服绩效详情" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && (
        <Card className="mb-3">
          <div className="flex items-end gap-2 px-page py-block-sm">
            <Input
              placeholder="staff_id"
              value={queryId}
              onChange={(e) => setQueryId(e.target.value)}
              className="w-44"
            />
          </div>
        </Card>
      )}
      {loading ? <LoadingState /> : p && <StatsGrid p={p} />}
    </PageContainer>
  );
}

// ── Route entry ───────────────────────────────────────────────────────────────

export function StaffPerformanceRoute() {
  const { staffId } = useParams();
  if (staffId) return <StaffPerformanceDetail staffId={staffId} />;
  return <StaffPerformanceOverview />;
}
