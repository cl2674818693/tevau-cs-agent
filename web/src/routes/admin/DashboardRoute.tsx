import { useEffect, useState } from "react";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from "recharts";
import {
  MessageSquare,
  UserCheck,
  ThumbsDown,
  Wrench,
  AlertTriangle,
} from "lucide-react";

import { getOverview, type DashboardOverview } from "../../api/adminDashboard";
import { KpiCard } from "../../components/admin/KpiCard";
import { Alert } from "../../components/ui/alert";
import { DatePicker } from "../../components/ui/date-picker";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { useStaffSession } from "../../hooks/useStaffSession";

function toUtcParam(d: Date): string {
  return d.toISOString().slice(0, 19).replace("T", " ");
}

function pct(x: number): string {
  return `${(x * 100).toFixed(1)}%`;
}

// Build fake single-point trend data from the aggregate for the chart.
// The API currently returns only aggregates, no time series, so we synthesise
// a bar chart of the six metrics so the chart area is still useful.
function buildBarData(d: DashboardOverview) {
  return [
    { name: "转人工", value: +(d.handoff_rate * 100).toFixed(1) },
    { name: "差评率", value: +(d.downvote_rate * 100).toFixed(1) },
    { name: "工具空结果", value: +(d.tool_empty_rate * 100).toFixed(1) },
  ];
}

function KpiSkeleton() {
  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-[100px] rounded-xl" />
      ))}
    </div>
  );
}

function ChartSkeleton() {
  return <Skeleton className="h-[300px] rounded-xl" />;
}

export function DashboardRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "manager" || role === "admin";

  const defaultFrom = new Date(Date.now() - 7 * 24 * 3600 * 1000);
  const defaultTo = new Date();

  const [fromDate, setFromDate] = useState<Date | undefined>(defaultFrom);
  const [toDate, setToDate] = useState<Date | undefined>(defaultTo);
  const [d, setD] = useState<DashboardOverview | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || !allowed) {
      setErr("需要管理权限");
      setLoading(false);
      return;
    }
    setLoading(true);
    setErr("");
    const opts: { from?: string; to?: string } = {};
    if (fromDate) opts.from = toUtcParam(fromDate);
    if (toDate) opts.to = toUtcParam(toDate);
    getOverview(token, opts)
      .then(setD)
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, fromDate, toDate]);

  const barData = d ? buildBarData(d) : [];

  return (
    <PageContainer width="wide">
      <PageHeader
        title="数据大盘"
        actions={
          <div className="flex items-center gap-2">
            <DatePicker date={fromDate} onChange={setFromDate} placeholder="开始日期" />
            <span className="text-sm text-muted-foreground">至</span>
            <DatePicker date={toDate} onChange={setToDate} placeholder="结束日期" />
          </div>
        }
      />

      {err && (
        <Alert variant="destructive" className="mb-4">
          {err}
        </Alert>
      )}

      {/* KPI 卡片 */}
      {loading ? (
        <KpiSkeleton />
      ) : d ? (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          <KpiCard
            label="会话总数"
            value={d.total_conversations.toLocaleString()}
            icon={MessageSquare}
          />
          <KpiCard
            label="转人工数"
            value={d.handoff.toLocaleString()}
            delta={pct(d.handoff_rate)}
            trend={d.handoff_rate > 0.3 ? "down" : "flat"}
            icon={UserCheck}
          />
          <KpiCard
            label="差评数"
            value={d.downvote.toLocaleString()}
            delta={pct(d.downvote_rate)}
            trend={d.downvote_rate > 0.2 ? "down" : "flat"}
            icon={ThumbsDown}
          />
          <KpiCard
            label="工具空结果率"
            value={pct(d.tool_empty_rate)}
            delta={`${d.tool_empty} / ${d.tool_calls} 次`}
            trend={d.tool_empty_rate > 0.3 ? "down" : "flat"}
            icon={Wrench}
          />
          <KpiCard
            label="超范围提问"
            value={d.out_of_scope.toLocaleString()}
            icon={AlertTriangle}
          />
          <KpiCard
            label="失败回合"
            value={d.failed_turns.toLocaleString()}
            trend={d.failed_turns > 0 ? "down" : "flat"}
            icon={AlertTriangle}
          />
        </div>
      ) : null}

      {/* 指标对比图 */}
      {!loading && d && (
        <div className="mt-6 rounded-md border border-border bg-card p-4">
          <p className="mb-3 text-sm font-medium text-muted-foreground">关键比率对比（%）</p>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={barData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
              <XAxis
                dataKey="name"
                className="text-xs"
                stroke="hsl(var(--muted-foreground))"
                tick={{ fontSize: 12 }}
              />
              <YAxis
                className="text-xs"
                stroke="hsl(var(--muted-foreground))"
                tick={{ fontSize: 12 }}
                unit="%"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--popover))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "0.5rem",
                }}
                formatter={(value) => [`${value}%`, ""]}
              />
              <Bar dataKey="value" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* 加载中时图表骨架 */}
      {loading && (
        <div className="mt-6">
          <ChartSkeleton />
        </div>
      )}
    </PageContainer>
  );
}
