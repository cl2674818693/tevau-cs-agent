import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getMatrix, type RbacMatrix, upsertMatrix } from "../../api/adminRbac";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

type LocalMatrix = Record<string, Record<string, boolean>>;

function MatrixGrid({
  matrix, roles, perms, onToggle,
}: {
  matrix: LocalMatrix; roles: string[]; perms: string[];
  onToggle: (role: string, perm: string, v: boolean) => void;
}) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-body3">
          <thead>
            <tr className="border-b border-line text-ink-secondary">
              <th className="px-3 py-2 text-left font-normal">模块</th>
              {roles.map((r) => (
                <th key={r} className="px-3 py-2 text-center font-normal">{r}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {perms.map((p) => (
              <tr key={p} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-ink-primary">{p}</td>
                {roles.map((r) => (
                  <td key={r} className="px-3 py-2 text-center">
                    <input type="checkbox" aria-label={`${p}/${r}`}
                      checked={matrix[r]?.[p] ?? false}
                      onChange={(e) => onToggle(r, p, e.target.checked)} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function RbacRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "admin";
  const [data, setData] = useState<RbacMatrix | null>(null);
  const [local, setLocal] = useState<LocalMatrix>({});
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!token || !allowed) { setErr("需要管理员权限"); setLoading(false); return; }
    setLoading(true);
    getMatrix(token)
      .then((d) => { setData(d); setLocal(d.matrix); })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  function toggle(r: string, p: string, v: boolean) {
    setLocal((prev) => ({ ...prev, [r]: { ...prev[r], [p]: v } }));
  }

  const items = useMemo(() => {
    if (!data) return [];
    return data.roles.flatMap((r) => data.permission_keys.map((p) => ({
      role: r, permission_key: p, allowed: local[r]?.[p] ? 1 : 0,
    })));
  }, [data, local]);

  async function save() {
    if (!token) return;
    setErr(""); setNotice("");
    try { await upsertMatrix(token, items); setNotice("已保存（缓存已刷新）"); }
    catch (e) { setErr(e instanceof Error ? e.message : "保存失败"); }
  }

  return (
    <PageContainer width="wide">
      <PageHeader title="角色权限（可编辑）" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {notice && <Alert variant="success" className="mb-2">{notice}</Alert>}
      <p className="mb-3 text-body3 text-ink-secondary">
        改完保存后，rbac.is_permitted 即时按新矩阵生效（缓存失效）。改角色仍走
        <Link to="/admin/staff" className="ml-1 text-brand">客服账号</Link>。
      </p>
      {loading ? <LoadingState /> : (allowed && data && (
        <>
          <MatrixGrid matrix={local} roles={data.roles} perms={data.permission_keys}
            onToggle={toggle} />
          <div className="mt-3"><Button size="md" onClick={save}>保存</Button></div>
        </>
      ))}
    </PageContainer>
  );
}
