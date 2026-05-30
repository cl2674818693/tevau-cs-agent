import { useEffect, useState } from "react";

import {
  createRule, deleteRule, listRules, type RoutingRule, setRuleActive,
} from "../../api/adminRoutingRules";
import { listGroups, type StaffGroup } from "../../api/adminStaffGroups";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

function RuleForm({ groups, onCreated, onError }: {
  groups: StaffGroup[]; onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [mt, setMt] = useState("user_type");
  const [mv, setMv] = useState("");
  const [tg, setTg] = useState(groups[0]?.id ?? 0);
  const [pr, setPr] = useState(100);
  async function submit() {
    if (!token || !mv || !tg) return;
    try {
      await createRule(token, { match_type: mt, match_value: mv, target_group_id: tg, priority: pr });
      setMv("");
      onCreated();
    } catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <select value={mt} onChange={(e) => setMt(e.target.value)}
          className="rounded border border-line px-2 py-1 text-body2">
          <option value="user_type">user_type</option>
          <option value="scope">scope</option>
          <option value="keyword">keyword</option>
        </select>
        <Input placeholder="匹配值（user_type=c/b/g；keyword=文本）" value={mv} className="w-60"
          onChange={(e) => setMv(e.target.value)} />
        <select value={tg} onChange={(e) => setTg(Number(e.target.value))}
          className="rounded border border-line px-2 py-1 text-body2">
          {groups.length === 0 ? <option value={0}>（先建分组）</option> : groups.map((g) => (
            <option key={g.id} value={g.id}>{g.name}</option>
          ))}
        </select>
        <Input type="number" min={1} value={pr} aria-label="priority" className="w-24"
          onChange={(e) => setPr(Number(e.target.value))} />
        <Button size="md" onClick={submit} disabled={!mv || !tg}>新建规则</Button>
      </div>
      <p className="px-page pb-block-sm text-footnote text-ink-tertiary">
        priority 越小越优先匹配。接入点见任务 4.5。
      </p>
    </Card>
  );
}

function RuleRow({ r, groupName, onChanged, onError }: {
  r: RoutingRule; groupName: (id: number) => string;
  onChanged: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  async function toggle() {
    if (!token) return;
    try { await setRuleActive(token, r.id, r.active ? 0 : 1); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "操作失败"); }
  }
  async function remove() {
    if (!token) return;
    try { await deleteRule(token, r.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2 text-ink-primary">{r.priority}</td>
      <td className="px-3 py-2">{r.match_type}</td>
      <td className="px-3 py-2 text-ink-secondary">{r.match_value}</td>
      <td className="px-3 py-2 text-ink-secondary">{groupName(r.target_group_id)}</td>
      <td className="px-3 py-2">{r.active ? "启用" : "停用"}</td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          <button className="text-brand" onClick={toggle}>{r.active ? "停用" : "启用"}</button>
          <button className="text-status-error" onClick={remove}>删除</button>
        </div>
      </td>
    </tr>
  );
}

function RulesTable({ rules, groups, onChanged, onError }: {
  rules: RoutingRule[]; groups: StaffGroup[];
  onChanged: () => void; onError: (m: string) => void;
}) {
  const groupName = (id: number) => groups.find((g) => g.id === id)?.name ?? `#${id}`;
  return (
    <Card className="mt-3">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">优先级</th>
            <th className="px-3 py-2 text-left font-normal">类型</th>
            <th className="px-3 py-2 text-left font-normal">匹配值</th>
            <th className="px-3 py-2 text-left font-normal">目标组</th>
            <th className="px-3 py-2 text-left font-normal">状态</th>
            <th className="px-3 py-2 text-left font-normal">操作</th>
          </tr>
        </thead>
        <tbody>
          {rules.length === 0 && (
            <tr><td colSpan={6} className="px-3 py-4 text-center text-ink-tertiary">无规则</td></tr>
          )}
          {rules.map((r) => (
            <RuleRow key={r.id} r={r} groupName={groupName} onChanged={onChanged} onError={onError} />
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function RoutingRulesRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [rules, setRules] = useState<RoutingRule[]>([]);
  const [groups, setGroups] = useState<StaffGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([listRules(token), listGroups(token)])
      .then(([rs, gs]) => { setRules(rs); setGroups(gs); })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管或管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="会话路由规则" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {loading ? <LoadingState /> : allowed && (
        <>
          <RuleForm groups={groups} onCreated={reload} onError={setErr} />
          <RulesTable rules={rules} groups={groups} onChanged={reload} onError={setErr} />
        </>
      )}
    </PageContainer>
  );
}
