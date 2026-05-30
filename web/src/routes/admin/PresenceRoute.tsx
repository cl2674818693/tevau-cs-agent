import { useEffect, useState } from "react";

import { listPresence, type Presence } from "../../api/staffPresence";
import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function PresenceTable({ rows, title }: { rows: Presence[]; title: string }) {
  return (
    <>
      <div className="mt-3 text-body2 font-medium text-ink-primary">{title}（{rows.length}）</div>
      <Card className="mt-2">
        <table className="w-full text-body3">
          <thead>
            <tr className="border-b border-line text-ink-secondary">
              <th className="px-3 py-2 text-left font-normal">staff_id</th>
              <th className="px-3 py-2 text-left font-normal">状态</th>
              <th className="px-3 py-2 text-left font-normal">上次活跃</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={3} className="px-3 py-4 text-center text-ink-tertiary">无</td></tr>
            )}
            {rows.map((p) => (
              <tr key={p.staff_id} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-ink-primary">{p.staff_id}</td>
                <td className="px-3 py-2">{p.status}</td>
                <td className="px-3 py-2 text-ink-tertiary">{p.last_seen_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}

export function PresenceRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [all, setAll] = useState<Presence[]>([]);
  const [active, setActive] = useState<Presence[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管或管理员权限"); setLoading(false); return; }
    listPresence(token)
      .then((d) => { setAll(d.all); setActive(d.active); })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="客服在线状态" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? <LoadingState /> : allowed && (
        <>
          <PresenceTable rows={active} title="在线（5 分钟内有心跳）" />
          <PresenceTable rows={all} title="全部" />
        </>
      )}
    </PageContainer>
  );
}
