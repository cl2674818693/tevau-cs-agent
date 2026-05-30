import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { getPerformance, type StaffPerformance } from "../../api/adminStaffPerformance";
import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

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

export function StaffPerformanceRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const { staffId: paramStaffId } = useParams();
  const [search, setSearch] = useSearchParams();
  const [staffId, setStaffId] = useState(paramStaffId ?? search.get("staff_id") ?? "");
  const [p, setP] = useState<StaffPerformance | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token || !allowed) {
      setErr("需要主管或管理员权限");
      return;
    }
    if (!staffId) return;
    setLoading(true);
    setErr("");
    getPerformance(token, staffId)
      .then(setP)
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, staffId]);

  return (
    <PageContainer width="wide">
      <PageHeader title="客服绩效详情" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && (
        <Card className="mb-3">
          <div className="flex items-end gap-2 px-page py-block-sm">
            <Input
              placeholder="staff_id"
              value={staffId}
              onChange={(e) => setStaffId(e.target.value)}
              className="w-44"
            />
            <button
              className="rounded bg-brand px-3 py-1 text-body3 text-ink-onbrand"
              onClick={() => {
                setSearch({ staff_id: staffId });
              }}
            >
              查询
            </button>
          </div>
        </Card>
      )}
      {loading ? <LoadingState /> : p && <StatsGrid p={p} />}
    </PageContainer>
  );
}
