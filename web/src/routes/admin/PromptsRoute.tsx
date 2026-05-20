import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getPromptVersions, setRollout } from "../../api/admin";
import { Button } from "../../components/ui/button";
import { useStaffSession } from "../../hooks/useStaffSession";

export function PromptsRoute() {
  const { token, role } = useStaffSession();
  const nav = useNavigate();
  const [versions, setVersions] = useState<string[]>([]);
  const [rollout, setRolloutState] = useState<Record<string, number>>({});
  const [notice, setNotice] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token || role !== "admin") {
      setErr("需要 admin 权限");
      return;
    }
    getPromptVersions(token)
      .then((d) => {
        setVersions(d.versions);
        setRolloutState(d.rollout);
      })
      .catch(() => setErr("加载失败"));
  }, [token, role]);

  const total = Object.values(rollout).reduce((a, b) => a + (b || 0), 0);

  async function save() {
    if (!token) return;
    setErr("");
    setNotice("");
    try {
      const next = await setRollout(token, rollout);
      setRolloutState(next);
      setNotice("已保存并热加载");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    }
  }

  return (
    <div className="mx-auto max-w-[560px] px-page py-block-lg">
      <div className="flex items-center mb-3">
        <h2 className="text-sh2 text-ink-primary flex-1">Prompt 灰度管理</h2>
        <button onClick={() => nav("/staff/conversations")} className="text-body3 text-ink-secondary">
          返回
        </button>
      </div>
      {err && <div className="text-body3 text-status-error mb-2">{err}</div>}
      {notice && <div className="text-body3 text-status-success mb-2">{notice}</div>}
      <div className="flex flex-col gap-2">
        {versions.map((v) => (
          <div key={v} className="flex items-center gap-3">
            <span className="text-body2 text-ink-primary flex-1">{v}</span>
            <input
              type="number"
              min={0}
              max={100}
              aria-label={`${v} 灰度比例`}
              value={rollout[v] ?? 0}
              onChange={(e) =>
                setRolloutState((prev) => ({ ...prev, [v]: Number(e.target.value) }))
              }
              className="w-20 rounded border border-line px-2 py-1 text-body2"
            />
            <span className="text-body3 text-ink-secondary">%</span>
          </div>
        ))}
      </div>
      <div className="text-footnote text-ink-secondary mt-2">
        合计 {total}%（≤100，余量回落 default）
      </div>
      <Button size="md" className="mt-3" onClick={save} disabled={total > 100}>
        保存
      </Button>
    </div>
  );
}
