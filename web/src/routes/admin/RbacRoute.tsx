import { Loader2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

import { getMatrix, type RbacMatrix, upsertMatrix } from "../../api/adminRbac";
import { Button } from "../../components/ui/button";
import { Checkbox } from "../../components/ui/checkbox";
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
    <div className="rounded-md border border-border p-4">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="px-3 py-2 text-left font-normal">模块</th>
              {roles.map((r) => (
                <th key={r} className="px-3 py-2 text-center font-normal">{r}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {perms.map((p) => (
              <tr key={p} className="border-b border-border last:border-0">
                <td className="px-3 py-2 text-foreground">{p}</td>
                {roles.map((r) => (
                  <td key={r} className="px-3 py-2 text-center">
                    <Checkbox
                      aria-label={`${p}/${r}`}
                      checked={matrix[r]?.[p] ?? false}
                      onCheckedChange={(v) => onToggle(r, p, v as boolean)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function RbacRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "admin";
  const [data, setData] = useState<RbacMatrix | null>(null);
  const [local, setLocal] = useState<LocalMatrix>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token || !allowed) { setLoading(false); return; }
    setLoading(true);
    getMatrix(token)
      .then((d) => { setData(d); setLocal(d.matrix); })
      .catch(() => toast.error("加载失败"))
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

  function reset() {
    if (data) setLocal(data.matrix);
  }

  async function save() {
    if (!token) return;
    setSaving(true);
    try {
      await upsertMatrix(token, items);
      toast.success("权限已保存");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageContainer width="wide">
      <PageHeader
        title="角色权限"
        actions={
          allowed && data ? (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={reset} disabled={saving}>
                重置
              </Button>
              <Button size="sm" onClick={save} disabled={saving}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                保存
              </Button>
            </div>
          ) : undefined
        }
      />
      <p className="mb-3 text-sm text-muted-foreground">
        改完保存后，rbac.is_permitted 即时按新矩阵生效（缓存失效）。改角色仍走
        <Link to="/admin/staff" className="ml-1 text-primary">客服账号</Link>。
      </p>
      {loading ? <LoadingState /> : (allowed && data && (
        <MatrixGrid matrix={local} roles={data.roles} perms={data.permission_keys}
          onToggle={toggle} />
      ))}
    </PageContainer>
  );
}
