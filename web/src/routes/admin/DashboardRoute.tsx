import { useEffect, useState } from "react";

import { getOverview, type DashboardOverview } from "../../api/adminDashboard";
import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function toUtcParam(d: Date): string {
  return d.toISOString().slice(0, 19).replace("T", " ");
}

function Stat({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <Card>
      <div className="flex flex-col gap-1 px-page py-block">
        <span className="text-footnote text-ink-secondary">{label}</span>
        <span className={`text-h3 ${danger ? "text-status-error" : "text-ink-primary"}`}>{value}</span>
      </div>
    </Card>
  );
}

function StatGrid({ d }: { d: DashboardOverview }) {
  const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
      <Stat label="会话总数" value={String(d.total_conversations)} />
      <Stat label="转人工率" value={pct(d.handoff_rate)} danger={d.handoff_rate > 0.3} />
      <Stat label="差评率" value={pct(d.downvote_rate)} danger={d.downvote_rate > 0.2} />
      <Stat label="工具空结果率" value={pct(d.tool_empty_rate)} danger={d.tool_empty_rate > 0.3} />
      <Stat label="超范围提问" value={String(d.out_of_scope)} />
      <Stat label="失败回合" value={String(d.failed_turns)} danger={d.failed_turns > 0} />
    </div>
  );
}

export function DashboardRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "manager" || role === "admin";
  const [d, setD] = useState<DashboardOverview | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || !allowed) { setErr("需要管理权限"); setLoading(false); return; }
    const from = toUtcParam(new Date(Date.now() - 7 * 24 * 3600 * 1000));
    getOverview(token, { from })
      .then(setD)
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="数据大盘（近 7 天）" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? <LoadingState /> : d && <StatGrid d={d} />}
    </PageContainer>
  );
}
