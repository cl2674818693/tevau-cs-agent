import { useEffect, useState } from "react";

import {
  createGroup,
  deleteGroup,
  listGroups,
  patchGroup,
  type StaffGroup,
} from "../../api/adminStaffGroups";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function GroupForm({
  onCreated,
  onError,
}: {
  onCreated: () => void;
  onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  async function submit() {
    if (!token || !name) return;
    try {
      await createGroup(token, { name, description: desc || undefined });
      setName("");
      setDesc("");
      onCreated();
    } catch (e) {
      onError(e instanceof Error ? e.message : "创建失败");
    }
  }
  return (
    <Card>
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <Input placeholder="分组名" value={name} className="w-44"
          onChange={(e) => setName(e.target.value)} />
        <Input placeholder="描述（可选）" value={desc} className="w-60"
          onChange={(e) => setDesc(e.target.value)} />
        <Button size="md" onClick={submit} disabled={!name}>新建分组</Button>
      </div>
    </Card>
  );
}

function GroupRow({
  g, onChanged, onError,
}: {
  g: StaffGroup;
  onChanged: () => void;
  onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  async function toggle() {
    if (!token) return;
    try { await patchGroup(token, g.id, { active: g.active ? 0 : 1 }); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "操作失败"); }
  }
  async function remove() {
    if (!token) return;
    try { await deleteGroup(token, g.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2 text-ink-primary">{g.id}</td>
      <td className="px-3 py-2 text-ink-primary">{g.name}</td>
      <td className="px-3 py-2 text-ink-secondary">{g.description ?? "—"}</td>
      <td className="px-3 py-2">{g.active ? "启用" : "停用"}</td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          <button className="text-brand" onClick={toggle}>{g.active ? "停用" : "启用"}</button>
          <button className="text-status-error" onClick={remove}>删除</button>
        </div>
      </td>
    </tr>
  );
}

export function StaffGroupsRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [groups, setGroups] = useState<StaffGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listGroups(token).then(setGroups).catch(() => setErr("加载失败")).finally(() => setLoading(false));
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

  return (
    <PageContainer width="wide">
      <PageHeader title="客服分组" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? (
        <LoadingState />
      ) : (
        allowed && (
          <>
            <GroupForm onCreated={reload} onError={setErr} />
            <Card className="mt-3">
              <table className="w-full text-body3">
                <thead>
                  <tr className="border-b border-line text-ink-secondary">
                    <th className="px-3 py-2 text-left font-normal">ID</th>
                    <th className="px-3 py-2 text-left font-normal">分组名</th>
                    <th className="px-3 py-2 text-left font-normal">描述</th>
                    <th className="px-3 py-2 text-left font-normal">状态</th>
                    <th className="px-3 py-2 text-left font-normal">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.length === 0 && (
                    <tr><td colSpan={5} className="px-3 py-4 text-center text-ink-tertiary">暂无分组</td></tr>
                  )}
                  {groups.map((g) => (
                    <GroupRow key={g.id} g={g} onChanged={reload} onError={setErr} />
                  ))}
                </tbody>
              </table>
            </Card>
          </>
        )
      )}
    </PageContainer>
  );
}
