import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { ColumnDef } from "@tanstack/react-table";
import { CheckCircle, XCircle, ShieldAlert, Clock } from "lucide-react";

import {
  createPolicy,
  deletePolicy,
  listBreaches,
  listPolicies,
  setPolicyActive,
  type SlaBreach,
  type SlaPolicy,
} from "../../api/adminSla";
import { KpiCard } from "../../components/admin/KpiCard";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { useStaffSession } from "../../hooks/useStaffSession";

const METRIC_LABEL: Record<string, string> = {
  take_time: "接管时长",
  resolve_time: "解决时长",
};

// ─── Skeletons ──────────────────────────────────────────────────────────────

function KpiSkeleton() {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <Skeleton key={i} className="h-[100px] rounded-xl" />
      ))}
    </div>
  );
}

function TableSkeleton() {
  return <Skeleton className="h-[220px] rounded-xl" />;
}

// ─── Policy form ─────────────────────────────────────────────────────────────

function PolicyForm({
  onCreated,
  onError,
}: {
  onCreated: () => void;
  onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [form, setForm] = useState({ metric: "take_time", threshold_seconds: 300 });
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!token) return;
    setSaving(true);
    try {
      await createPolicy(token, {
        metric: form.metric,
        threshold_seconds: Number(form.threshold_seconds),
        scope: "all",
      });
      onCreated();
    } catch (e) {
      onError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-wrap items-end gap-2">
      <select
        value={form.metric}
        onChange={(e) => setForm({ ...form, metric: e.target.value })}
        className="rounded-md border border-input bg-background px-3 py-1.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <option value="take_time">接管时长</option>
        <option value="resolve_time">解决时长</option>
      </select>
      <Input
        type="number"
        min={1}
        value={form.threshold_seconds}
        onChange={(e) => setForm({ ...form, threshold_seconds: Number(e.target.value) })}
        className="w-28"
        aria-label="阈值秒数"
      />
      <span className="text-sm text-muted-foreground">秒</span>
      <Button size="sm" onClick={submit} disabled={saving}>
        {saving ? "保存中…" : "新增策略"}
      </Button>
    </div>
  );
}

// ─── KPI derivation ──────────────────────────────────────────────────────────

function deriveKpi(policies: SlaPolicy[], breaches: SlaBreach[]) {
  const active = policies.filter((p) => p.active);
  const breachCount = breaches.length;
  // compliance rate: 无 active 策略时返回 null（UI 显示 "—"），避免 0/0 误读为 100%
  const breachedMetrics = new Set(breaches.map((b) => b.metric));
  const compliantCount = active.filter((p) => !breachedMetrics.has(p.metric)).length;
  const complianceRate =
    active.length > 0 ? (compliantCount / active.length) * 100 : null;

  const avgThreshold =
    active.length > 0
      ? Math.round(active.reduce((s, p) => s + p.threshold_seconds, 0) / active.length)
      : null;

  return { complianceRate, avgThreshold, breachCount };
}

// ─── Main route ───────────────────────────────────────────────────────────────

export function SlaRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";

  const [policies, setPolicies] = useState<SlaPolicy[]>([]);
  const [breaches, setBreaches] = useState<SlaBreach[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [actionErr, setActionErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    setErr("");
    Promise.all([listPolicies(token), listBreaches(token)])
      .then(([p, b]) => {
        setPolicies(p);
        setBreaches(b);
      })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setErr("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  const kpi = useMemo(() => deriveKpi(policies, breaches), [policies, breaches]);

  // ── Policy table columns ──────────────────────────────────────────────────

  const policyCols: ColumnDef<SlaPolicy>[] = useMemo(
    () => [
      {
        accessorKey: "metric",
        header: "指标",
        cell: ({ row }) => METRIC_LABEL[row.original.metric] ?? row.original.metric,
      },
      {
        accessorKey: "threshold_seconds",
        header: "阈值（秒）",
        cell: ({ row }) => row.original.threshold_seconds,
      },
      {
        accessorKey: "active",
        header: "状态",
        cell: ({ row }) =>
          row.original.active ? (
            <Badge variant="outline" className="text-emerald-600 border-emerald-400">
              启用
            </Badge>
          ) : (
            <Badge variant="outline" className="text-muted-foreground">
              停用
            </Badge>
          ),
      },
      {
        id: "actions",
        header: "操作",
        cell: ({ row }) => {
          const p = row.original;
          async function toggle() {
            if (!token) return;
            try {
              await setPolicyActive(token, p.id, p.active ? 0 : 1);
              reload();
            } catch (e) {
              setActionErr(e instanceof Error ? e.message : "操作失败");
            }
          }
          async function remove() {
            if (!token) return;
            try {
              await deletePolicy(token, p.id);
              reload();
            } catch (e) {
              setActionErr(e instanceof Error ? e.message : "删除失败");
            }
          }
          return (
            <div className="flex gap-3 text-sm">
              <button
                className="text-primary hover:underline"
                onClick={toggle}
              >
                {p.active ? "停用" : "启用"}
              </button>
              <button
                className="text-destructive hover:underline"
                onClick={remove}
              >
                删除
              </button>
            </div>
          );
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token],
  );

  // ── Breach table columns ──────────────────────────────────────────────────

  const breachCols: ColumnDef<SlaBreach>[] = useMemo(
    () => [
      {
        accessorKey: "conversation_id",
        header: "会话",
        cell: ({ row }) => (
          <Link
            className="text-primary hover:underline"
            to={`/staff/conversations/${row.original.conversation_id}`}
          >
            #{row.original.conversation_id}
          </Link>
        ),
      },
      {
        accessorKey: "metric",
        header: "指标",
        cell: ({ row }) => METRIC_LABEL[row.original.metric] ?? row.original.metric,
      },
      {
        accessorKey: "elapsed_seconds",
        header: "已用时（秒）",
        cell: ({ row }) => row.original.elapsed_seconds,
      },
      {
        accessorKey: "threshold_seconds",
        header: "阈值（秒）",
        cell: ({ row }) => row.original.threshold_seconds,
      },
      {
        id: "overrun",
        header: "超出（秒）",
        cell: ({ row }) => (
          <span className="text-destructive font-medium">
            +{row.original.elapsed_seconds - row.original.threshold_seconds}
          </span>
        ),
      },
    ],
    [],
  );

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <PageContainer width="wide">
      <PageHeader
        title="SLA"
        actions={
          allowed && !loading ? (
            <PolicyForm onCreated={reload} onError={setActionErr} />
          ) : undefined
        }
      />

      {err && (
        <Alert variant="destructive" className="mb-4">
          {err}
        </Alert>
      )}
      {actionErr && (
        <Alert variant="destructive" className="mb-4">
          {actionErr}
        </Alert>
      )}

      {/* KPI 卡片 */}
      {loading ? (
        <KpiSkeleton />
      ) : (
        <div className="grid gap-3 md:grid-cols-3">
          <KpiCard
            label="达标率"
            value={kpi.complianceRate === null ? "—" : `${kpi.complianceRate.toFixed(1)}%`}
            trend={kpi.complianceRate === null ? "flat" : kpi.complianceRate >= 80 ? "up" : "down"}
            icon={CheckCircle}
          />
          <KpiCard
            label="平均响应阈值"
            value={kpi.avgThreshold === null ? "—" : `${kpi.avgThreshold}s`}
            icon={Clock}
          />
          <KpiCard
            label="未达标数"
            value={kpi.breachCount}
            trend={kpi.breachCount > 0 ? "down" : "flat"}
            icon={kpi.breachCount > 0 ? XCircle : ShieldAlert}
          />
        </div>
      )}

      {/* 当前超时告警 */}
      {!loading && breaches.length > 0 && (
        <Alert variant="destructive" className="mt-4">
          当前 {breaches.length} 个会话超时未处理
        </Alert>
      )}

      {/* 策略列表 */}
      <div className="mt-6">
        <p className="mb-3 text-sm font-medium text-muted-foreground">SLA 策略</p>
        {loading ? (
          <TableSkeleton />
        ) : (
          <DataTable
            columns={policyCols}
            data={policies}
            empty="暂无策略，请在右上角新增"
          />
        )}
      </div>

      {/* 超时会话列表 */}
      {(!loading && (breaches.length > 0 || !loading)) && (
        <div className="mt-6">
          <p className="mb-3 text-sm font-medium text-muted-foreground">当前超时会话</p>
          {loading ? (
            <TableSkeleton />
          ) : (
            <DataTable
              columns={breachCols}
              data={breaches}
              empty="无超时会话"
            />
          )}
        </div>
      )}
    </PageContainer>
  );
}
