import { useEffect, useState } from "react";
import { ArrowLeftRight, CheckCircle, Clock, UserCheck } from "lucide-react";

import { getKpi, type StaffKpi } from "../../api/staff";
import { KpiCard } from "../../components/admin/KpiCard";
import { Alert } from "../../components/ui/alert";
import { DatePicker } from "../../components/ui/date-picker";
import { EmptyState } from "../../components/ui/empty-state";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { useStaffSession } from "../../hooks/useStaffSession";

function toUtcParam(d: Date): string {
  return d.toISOString().slice(0, 19).replace("T", " ");
}

function fmtDuration(seconds: number): string {
  if (seconds <= 0) return "-";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}分${s}秒` : `${s}秒`;
}

function KpiSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-[100px] rounded-xl" />
      ))}
    </div>
  );
}

export function KpiRoute() {
  const { token, staffId } = useStaffSession();

  const defaultFrom = new Date(Date.now() - 7 * 24 * 3600 * 1000);
  const defaultTo = new Date();

  const [fromDate, setFromDate] = useState<Date | undefined>(defaultFrom);
  const [toDate, setToDate] = useState<Date | undefined>(defaultTo);
  const [kpi, setKpi] = useState<StaffKpi | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    setError("");
    const opts: { from?: string; to?: string } = {};
    if (fromDate) opts.from = toUtcParam(fromDate);
    if (toDate) opts.to = toUtcParam(toDate);
    getKpi(token, opts)
      .then((res) => {
        const mine = staffId ? res.staff.find((r) => r.staff_id === staffId) ?? null : null;
        setKpi(mine);
      })
      .catch(() => setError("加载失败"))
      .finally(() => setLoading(false));
  }, [token, staffId, fromDate, toDate]);

  return (
    <PageContainer width="wide">
      <PageHeader
        title="我的 KPI"
        actions={
          <div className="flex items-center gap-2">
            <DatePicker date={fromDate} onChange={setFromDate} placeholder="开始日期" />
            <span className="text-sm text-muted-foreground">至</span>
            <DatePicker date={toDate} onChange={setToDate} placeholder="结束日期" />
          </div>
        }
      />

      {error && (
        <Alert variant="error" className="mb-4">
          {error}
        </Alert>
      )}

      {loading ? (
        <KpiSkeleton />
      ) : kpi ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard
            label="接管数"
            value={kpi.takeovers.toLocaleString()}
            icon={UserCheck}
          />
          <KpiCard
            label="解决数"
            value={kpi.resolved.toLocaleString()}
            delta={`解决率 ${(kpi.resolved_ratio * 100).toFixed(0)}%`}
            trend={kpi.resolved_ratio >= 0.7 ? "up" : "down"}
            icon={CheckCircle}
          />
          <KpiCard
            label="转派数"
            value={(kpi.transfers ?? 0).toLocaleString()}
            delta={
              kpi.transfer_ratio != null
                ? `转派率 ${(kpi.transfer_ratio * 100).toFixed(0)}%`
                : undefined
            }
            trend={
              kpi.transfer_ratio != null
                ? kpi.transfer_ratio > 0.3
                  ? "down"
                  : "flat"
                : "flat"
            }
            icon={ArrowLeftRight}
          />
          <KpiCard
            label="平均处理时长"
            value={fmtDuration(kpi.avg_handle_seconds)}
            icon={Clock}
          />
        </div>
      ) : (
        <EmptyState>该时间段内暂无数据</EmptyState>
      )}
    </PageContainer>
  );
}
