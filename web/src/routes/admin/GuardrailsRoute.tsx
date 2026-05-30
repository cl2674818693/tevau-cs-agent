import { useEffect, useState } from "react";

import {
  createGuardrail, deleteGuardrail, type Guardrail, listGuardrails, setGuardrailActive,
} from "../../api/adminGuardrails";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

const TYPES = ["blocklist", "sensitive_word", "scope_toggle"];

function RuleForm({ onCreated, onError }: {
  onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [type, setType] = useState("sensitive_word");
  const [pattern, setPattern] = useState("");
  const [action, setAction] = useState("block");
  async function submit() {
    if (!token || !pattern) return;
    try {
      await createGuardrail(token, { type, pattern, action });
      setPattern("");
      onCreated();
    } catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <select value={type} onChange={(e) => setType(e.target.value)}
          className="rounded border border-line px-2 py-1 text-body2">
          {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <Input placeholder="pattern（subject_id / 词 / scope 名）" value={pattern} className="w-72"
          onChange={(e) => setPattern(e.target.value)} />
        <select value={action} onChange={(e) => setAction(e.target.value)}
          className="rounded border border-line px-2 py-1 text-body2">
          <option value="block">block</option>
          <option value="flag">flag</option>
        </select>
        <Button size="md" onClick={submit} disabled={!pattern}>新建规则</Button>
      </div>
    </Card>
  );
}

function RuleRow({ g, onChanged, onError }: {
  g: Guardrail; onChanged: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  async function toggle() {
    if (!token) return;
    try { await setGuardrailActive(token, g.id, g.active ? 0 : 1); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "操作失败"); }
  }
  async function rm() {
    if (!token) return;
    try { await deleteGuardrail(token, g.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2">{g.id}</td>
      <td className="px-3 py-2">{g.type}</td>
      <td className="px-3 py-2 text-ink-primary">{g.pattern}</td>
      <td className="px-3 py-2">{g.action}</td>
      <td className="px-3 py-2">{g.active ? "启用" : "停用"}</td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          <button className="text-brand" onClick={toggle}>{g.active ? "停用" : "启用"}</button>
          <button className="text-status-error" onClick={rm}>删除</button>
        </div>
      </td>
    </tr>
  );
}

function RulesTable({ rules, onChanged, onError }: {
  rules: Guardrail[]; onChanged: () => void; onError: (m: string) => void;
}) {
  return (
    <Card className="mt-3">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">ID</th>
            <th className="px-3 py-2 text-left font-normal">类型</th>
            <th className="px-3 py-2 text-left font-normal">pattern</th>
            <th className="px-3 py-2 text-left font-normal">动作</th>
            <th className="px-3 py-2 text-left font-normal">状态</th>
            <th className="px-3 py-2 text-left font-normal">操作</th>
          </tr>
        </thead>
        <tbody>
          {rules.length === 0 && (
            <tr><td colSpan={6} className="px-3 py-4 text-center text-ink-tertiary">无规则</td></tr>
          )}
          {rules.map((g) => <RuleRow key={g.id} g={g} onChanged={onChanged} onError={onError} />)}
        </tbody>
      </table>
      <p className="px-page py-block-sm text-footnote text-ink-tertiary">
        evaluate_guardrails helper 已就绪。chat.py 入口接入留 M4。
      </p>
    </Card>
  );
}

export function GuardrailsRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";
  const [rules, setRules] = useState<Guardrail[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listGuardrails(token).then(setRules).catch(() => setErr("加载失败")).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要工程或管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  return (
    <PageContainer width="wide">
      <PageHeader title="范围与拦截配置" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && <RuleForm onCreated={reload} onError={setErr} />}
      {loading ? <LoadingState /> : allowed && (
        <RulesTable rules={rules} onChanged={reload} onError={setErr} />
      )}
    </PageContainer>
  );
}
