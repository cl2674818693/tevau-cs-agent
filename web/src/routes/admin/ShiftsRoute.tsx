import { useEffect, useState } from "react";

import { createShift, deleteShift, listShifts, type Shift } from "../../api/adminShifts";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function ShiftForm({ onCreated, onError }: {
  onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [staffId, setStaffId] = useState("");
  const [start, setStart] = useState("2026-06-01 09:00:00");
  const [end, setEnd] = useState("2026-06-01 18:00:00");
  async function submit() {
    if (!token || !staffId) return;
    try { await createShift(token, { staff_id: staffId, start_at: start, end_at: end }); onCreated(); }
    catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <Input placeholder="staff_id" value={staffId} className="w-32"
          onChange={(e) => setStaffId(e.target.value)} />
        <Input placeholder="start UTC" value={start} className="w-44"
          onChange={(e) => setStart(e.target.value)} />
        <Input placeholder="end UTC" value={end} className="w-44"
          onChange={(e) => setEnd(e.target.value)} />
        <Button size="md" onClick={submit} disabled={!staffId}>新建排班</Button>
      </div>
      <p className="px-page pb-block-sm text-footnote text-ink-tertiary">
        时间格式："YYYY-MM-DD HH:MM:SS" UTC（与后端 now_str 一致）。
      </p>
    </Card>
  );
}

function ShiftRow({ s, onRemoved, onError }: {
  s: Shift; onRemoved: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  async function remove() {
    if (!token) return;
    try { await deleteShift(token, s.id); onRemoved(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2">{s.id}</td>
      <td className="px-3 py-2 text-ink-primary">{s.staff_id}</td>
      <td className="px-3 py-2 text-ink-secondary">{s.start_at}</td>
      <td className="px-3 py-2 text-ink-secondary">{s.end_at}</td>
      <td className="px-3 py-2">
        <button className="text-status-error" onClick={remove}>删除</button>
      </td>
    </tr>
  );
}

function ShiftsTable({ shifts, onRemoved, onError }: {
  shifts: Shift[]; onRemoved: () => void; onError: (m: string) => void;
}) {
  return (
    <Card className="mt-3">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">ID</th>
            <th className="px-3 py-2 text-left font-normal">staff_id</th>
            <th className="px-3 py-2 text-left font-normal">开始</th>
            <th className="px-3 py-2 text-left font-normal">结束</th>
            <th className="px-3 py-2 text-left font-normal">操作</th>
          </tr>
        </thead>
        <tbody>
          {shifts.length === 0 && (
            <tr><td colSpan={5} className="px-3 py-4 text-center text-ink-tertiary">无</td></tr>
          )}
          {shifts.map((s) => <ShiftRow key={s.id} s={s} onRemoved={onRemoved} onError={onError} />)}
        </tbody>
      </table>
    </Card>
  );
}

export function ShiftsRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [filter, setFilter] = useState("");
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listShifts(token, filter ? { staff_id: filter } : undefined)
      .then(setShifts).catch(() => setErr("加载失败")).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管或管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, filter]);

  return (
    <PageContainer width="wide">
      <PageHeader title="排班" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && (
        <>
          <ShiftForm onCreated={reload} onError={setErr} />
          <Card className="mt-3">
            <div className="flex items-end gap-2 px-page py-block-sm">
              <Input placeholder="按 staff_id 过滤" value={filter} className="w-44"
                onChange={(e) => setFilter(e.target.value)} />
            </div>
          </Card>
          {loading ? <LoadingState /> : <ShiftsTable shifts={shifts} onRemoved={reload} onError={setErr} />}
        </>
      )}
    </PageContainer>
  );
}
