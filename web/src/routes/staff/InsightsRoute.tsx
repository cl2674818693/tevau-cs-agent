import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getKnowledgeGaps, type KnowledgeGaps } from "../../api/staff";
import { useStaffSession } from "../../hooks/useStaffSession";

const CARDS: { key: keyof KnowledgeGaps; label: string; hint: string }[] = [
  { key: "out_of_scope", label: "范围外", hint: "话题分类判为 no（AI 答不了/超范围）" },
  { key: "failed_turns", label: "失败回合", hint: "LLM/工具失败或僵尸超时被标 failed" },
  { key: "thumbs_down", label: "差评 👎", hint: "用户对 AI 回复点踩" },
];

export function InsightsRoute() {
  const { token } = useStaffSession();
  const nav = useNavigate();
  const [gaps, setGaps] = useState<KnowledgeGaps | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    getKnowledgeGaps(token)
      .then(setGaps)
      .catch(() => setErr("加载失败"));
  }, [token, nav]);

  return (
    <div className="mx-auto max-w-[720px] px-page py-block-lg">
      <div className="flex items-center mb-3">
        <h2 className="text-sh2 text-ink-primary flex-1">知识缺口报表</h2>
        <Link to="/staff/conversations" className="text-body3 text-ink-secondary">
          返回工作台
        </Link>
      </div>
      {err && <div className="text-body3 text-status-error mb-2">{err}</div>}
      <div className="grid grid-cols-3 gap-3">
        {CARDS.map((c) => (
          <div key={c.key} className="rounded border border-line bg-surface-card px-3 py-4">
            <div className="text-sh1 text-ink-primary">{gaps ? gaps[c.key] : "-"}</div>
            <div className="text-body2 text-ink-primary mt-1">{c.label}</div>
            <div className="text-footnote text-ink-secondary mt-1">{c.hint}</div>
          </div>
        ))}
      </div>
      <p className="text-footnote text-ink-secondary mt-4">
        口径：全部历史。明细可在「全局工具审计」或具体会话的留痕页查看。
      </p>
    </div>
  );
}
