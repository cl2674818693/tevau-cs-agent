import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  createPolicy,
  deletePolicy,
  listBreaches,
  listPolicies,
  setPolicyActive,
  type SlaBreach,
  type SlaPolicy,
} from "../../api/adminSla";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

const METRIC_LABEL: Record<string, string> = {
  take_time: "接管时长",
  resolve_time: "解决时长",
};

function PolicyForm({
  onCreated,
  onError,
}: {
  onCreated: () => void;
  onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [form, setForm] = useState({ metric: "take_time", threshold_seconds: 300 });

  async function submit() {
    if (!token) return;
    try {
      await createPolicy(token, {
        metric: form.metric,
        threshold_seconds: Number(form.threshold_seconds),
        scope: "all",
      });
      onCreated();
    } catch (e) {
      onError(e instanceof Error ? e.message : "创建失败");
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-end gap-2 px-page py-block-sm">
        <select
          value={form.metric}
          onChange={(e) => setForm({ ...form, metric: e.target.value })}
          className="rounded border border-line px-2 py-1 text-body2"
        >
          <option value="take_time">接管时长</option>
          <option value="resolve_time">解决时长</option>
        </select>
        <Input
          type="number"
          min={1}
          value={form.threshold_seconds}
          onChange={(e) => setForm({ ...form, threshold_seconds: Number(e.target.value) })}
          className="w-28"
          aria-label="阈值秒数"
        />
        <span className="text-body3 text-ink-secondary">秒</span>
        <Button size="md" onClick={submit}>
          新增策略
        </Button>
      </div>
    </Card>
  );
}

function PoliciesTable({
  rows,
  onChanged,
  onError,
}: {
  rows: SlaPolicy[];
  onChanged: () => void;
  onError: (m: string) => void;
}) {
  const { token } = useStaffSession();

  async function toggle(p: SlaPolicy) {
    if (!token) return;
    try {
      await setPolicyActive(token, p.id, p.active ? 0 : 1);
      onChanged();
    } catch (e) {
      onError(e instanceof Error ? e.message : "操作失败");
    }
  }

  async function remove(p: SlaPolicy) {
    if (!token) return;
    try {
      await deletePolicy(token, p.id);
      onChanged();
    } catch (e) {
      onError(e instanceof Error ? e.message : "删除失败");
    }
  }

  return (
    <Card className="mt-2">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">指标</th>
            <th className="px-3 py-2 text-right font-normal">阈值(秒)</th>
            <th className="px-3 py-2 text-left font-normal">状态</th>
            <th className="px-3 py-2 text-left font-normal">操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id} className="border-b border-line last:border-0">
              <td className="px-3 py-2 text-ink-primary">{METRIC_LABEL[p.metric] ?? p.metric}</td>
              <td className="px-3 py-2 text-right text-ink-secondary">{p.threshold_seconds}</td>
              <td className="px-3 py-2">{p.active ? "启用" : "停用"}</td>
              <td className="px-3 py-2">
                <div className="flex gap-2">
                  <button className="text-brand" onClick={() => toggle(p)}>
                    {p.active ? "停用" : "启用"}
                  </button>
                  <button className="text-status-error" onClick={() => remove(p)}>
                    删除
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function BreachesList({ breaches }: { breaches: SlaBreach[] }) {
  return (
    <Card className="mt-2">
      <ul className="flex flex-col">
        {breaches.length === 0 && (
          <li className="px-page py-block-sm text-ink-tertiary">无</li>
        )}
        {breaches.map((b, i) => (
          <li
            key={i}
            className="flex justify-between border-b border-line px-page py-block-sm last:border-0"
          >
            <Link className="text-brand" to={`/staff/conversations/${b.conversation_id}`}>
              会话 #{b.conversation_id}
            </Link>
            <span className="text-status-error">
              {METRIC_LABEL[b.metric]} 已 {b.elapsed_seconds}s / 阈值 {b.threshold_seconds}s
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function SlaRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "admin";
  const [policies, setPolicies] = useState<SlaPolicy[]>([]);
  const [breaches, setBreaches] = useState<SlaBreach[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    Promise.all([listPolicies(token), listBreaches(token)])
      .then(([p, b]) => {
        setPolicies(p);
        setBreaches(b);
      })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
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
      <PageHeader title="SLA 配置与告警" />
      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}
      {loading ? (
        <LoadingState />
      ) : (
        allowed && (
          <>
            {breaches.length > 0 && (
              <Alert variant="error" className="mb-3">
                当前 {breaches.length} 个会话超时未处理
              </Alert>
            )}
            <PolicyForm onCreated={reload} onError={setErr} />
            <div className="mt-4 text-body2 font-medium text-ink-primary">策略</div>
            <PoliciesTable rows={policies} onChanged={reload} onError={setErr} />
            <div className="mt-4 text-body2 font-medium text-ink-primary">当前超时会话</div>
            <BreachesList breaches={breaches} />
          </>
        )
      )}
    </PageContainer>
  );
}
