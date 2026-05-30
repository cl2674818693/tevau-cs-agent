import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { createStaff, listStaff, patchStaff, resetPassword, STAFF_ROLES, type StaffRow } from "../../api/adminStaff";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

type CreateForm = { staff_id: string; display_name: string; role: string; password: string };
type StaffTableProps = { rows: StaffRow[]; onRefresh: () => void; onNotice: (msg: string) => void; onError: (msg: string) => void };

function CreateStaffForm({ onCreated }: { onCreated: () => void }) {
  const { token } = useStaffSession();
  const [form, setForm] = useState<CreateForm>({ staff_id: "", display_name: "", role: "agent", password: "" });
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");

  async function onCreate() {
    if (!token) return;
    setErr("");
    setNotice("");
    try {
      await createStaff(token, form);
      setForm({ staff_id: "", display_name: "", role: "agent", password: "" });
      setNotice("已创建");
      onCreated();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "创建失败");
    }
  }

  return (
    <>
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {notice && <Alert variant="success" className="mb-2">{notice}</Alert>}
      <Card>
        <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
          <Input placeholder="staff_id" value={form.staff_id}
            onChange={(e) => setForm({ ...form, staff_id: e.target.value })} className="w-32" />
          <Input placeholder="显示名" value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })} className="w-32" />
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="rounded border border-line px-2 py-1 text-body2">
            {STAFF_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <Input type="password" placeholder="初始密码" value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} className="w-32" />
          <Button size="md" onClick={onCreate}
            disabled={!form.staff_id || !form.display_name || !form.password}>新建</Button>
        </div>
      </Card>
    </>
  );
}

function StaffTable({ rows, onRefresh, onNotice, onError }: StaffTableProps) {
  const { token } = useStaffSession();

  async function onChangeRole(staffId: string, newRole: string) {
    if (!token) return;
    try {
      await patchStaff(token, staffId, { role: newRole });
      onRefresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : "操作失败");
    }
  }

  async function onToggleActive(s: StaffRow) {
    if (!token) return;
    try {
      await patchStaff(token, s.staff_id, { active: s.active ? 0 : 1 });
      onRefresh();
    } catch (e) {
      onError(e instanceof Error ? e.message : "操作失败");
    }
  }

  async function onReset(staffId: string) {
    if (!token) return;
    const pw = window.prompt(`为 ${staffId} 设置新密码`);
    if (!pw) return;
    try {
      await resetPassword(token, staffId, pw);
      onNotice("密码已重置");
    } catch (e) {
      onError(e instanceof Error ? e.message : "操作失败");
    }
  }

  return (
    <Card className="mt-3">
      <div className="overflow-x-auto">
        <table className="w-full text-body3">
          <thead>
            <tr className="border-b border-line text-ink-secondary">
              <th className="px-3 py-2 text-left font-normal">staff_id</th>
              <th className="px-3 py-2 text-left font-normal">显示名</th>
              <th className="px-3 py-2 text-left font-normal">角色</th>
              <th className="px-3 py-2 text-left font-normal">状态</th>
              <th className="px-3 py-2 text-left font-normal">操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.staff_id} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-ink-primary">{s.staff_id}</td>
                <td className="px-3 py-2 text-ink-secondary">{s.display_name}</td>
                <td className="px-3 py-2">
                  <select value={s.role} onChange={(e) => onChangeRole(s.staff_id, e.target.value)}
                    className="rounded border border-line px-1 py-0.5">
                    {STAFF_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </td>
                <td className="px-3 py-2">
                  <span className={s.active ? "text-status-success" : "text-ink-tertiary"}>
                    {s.active ? "启用" : "停用"}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <div className="flex gap-2">
                    <button className="text-brand" onClick={() => onToggleActive(s)}>
                      {s.active ? "停用" : "启用"}
                    </button>
                    <button className="text-brand" onClick={() => onReset(s.staff_id)}>重置密码</button>
                    <Link className="text-brand" to={`/admin/performance/${s.staff_id}`}>绩效</Link>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function StaffAccountsRoute() {
  const { token, role } = useStaffSession();
  const [rows, setRows] = useState<StaffRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listStaff(token)
      .then(setRows)
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || role !== "admin") {
      setErr("需要 admin 权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="客服账号" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {notice && <Alert variant="success" className="mb-2">{notice}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        role === "admin" && (
          <>
            <CreateStaffForm onCreated={reload} />
            <StaffTable rows={rows} onRefresh={reload} onNotice={setNotice} onError={setErr} />
          </>
        )
      )}
    </PageContainer>
  );
}
