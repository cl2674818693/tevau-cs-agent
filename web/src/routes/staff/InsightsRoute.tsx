import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  getGapConversations,
  getKnowledgeGaps,
  getToolHealth,
  type GapConversation,
  type GapKind,
  type InsightsRange,
  type KnowledgeGaps,
  type ToolHealth,
} from "../../api/staff";
import { useStaffSession } from "../../hooks/useStaffSession";

const CARDS: { key: keyof KnowledgeGaps; kind: GapKind; label: string; hint: string }[] = [
  {
    key: "out_of_scope",
    kind: "out_of_scope",
    label: "范围外",
    hint: "话题分类判为 no（AI 答不了/超范围）",
  },
  {
    key: "failed_turns",
    kind: "failed",
    label: "失败回合",
    hint: "LLM/工具失败或僵尸超时被标 failed",
  },
  { key: "thumbs_down", kind: "thumbs_down", label: "差评 👎", hint: "用户对 AI 回复点踩" },
  {
    key: "human_handoff",
    kind: "human_handoff",
    label: "转人工",
    hint: "会话从 AI 切换到人工接管",
  },
];

type RangeKey = "7d" | "30d" | "all";

const RANGE_OPTIONS: { key: RangeKey; label: string }[] = [
  { key: "7d", label: "近 7 天" },
  { key: "30d", label: "近 30 天" },
  { key: "all", label: "全部" },
];

function rangeOf(key: RangeKey): InsightsRange {
  if (key === "all") return {};
  const days = key === "7d" ? 7 : 30;
  const from = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  // 后端按 created_at 字符串字典序比较，格式必须匹配 now_str()："YYYY-MM-DD HH:MM:SS"(UTC,无T无Z)
  return { from: from.toISOString().slice(0, 19).replace("T", " ") };
}

function rangeLabel(key: RangeKey): string {
  return RANGE_OPTIONS.find((o) => o.key === key)?.label ?? "";
}

// eslint-disable-next-line max-lines-per-function -- 报表页：时间窗 + 四卡片下钻 + 工具健康表
export function InsightsRoute() {
  const { token } = useStaffSession();
  const nav = useNavigate();
  const [rangeKey, setRangeKey] = useState<RangeKey>("7d");
  const [gaps, setGaps] = useState<KnowledgeGaps | null>(null);
  const [tools, setTools] = useState<ToolHealth[]>([]);
  const [err, setErr] = useState("");

  // 下钻：当前展开的卡片 + 其会话清单
  const [openKind, setOpenKind] = useState<GapKind | null>(null);
  const [drillRows, setDrillRows] = useState<GapConversation[]>([]);
  const [drillLoading, setDrillLoading] = useState(false);

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    const range = rangeOf(rangeKey);
    setOpenKind(null);
    setDrillRows([]);
    Promise.all([getKnowledgeGaps(token, range), getToolHealth(token, range)])
      .then(([g, t]) => {
        setGaps(g);
        setTools(t);
        setErr("");
      })
      .catch(() => setErr("加载失败"));
  }, [token, rangeKey, nav]);

  const drill = useCallback(
    (kind: GapKind) => {
      if (!token) return;
      if (openKind === kind) {
        setOpenKind(null);
        return;
      }
      setOpenKind(kind);
      setDrillRows([]);
      setDrillLoading(true);
      getGapConversations(token, kind, { ...rangeOf(rangeKey), limit: 50 })
        .then(setDrillRows)
        .catch(() => setErr("下钻加载失败"))
        .finally(() => setDrillLoading(false));
    },
    [token, openKind, rangeKey],
  );

  return (
    <div className="mx-auto max-w-[860px] px-page py-block-lg">
      <div className="flex items-center mb-3">
        <h2 className="text-sh2 text-ink-primary flex-1">知识缺口报表</h2>
        <Link to="/staff/conversations" className="text-body3 text-ink-secondary">
          返回工作台
        </Link>
      </div>

      <div className="flex items-center gap-2 mb-3 text-body3">
        {RANGE_OPTIONS.map((o) => (
          <button
            key={o.key}
            type="button"
            onClick={() => setRangeKey(o.key)}
            className={
              rangeKey === o.key
                ? "rounded border border-brand bg-brand/10 px-3 py-1 text-brand"
                : "rounded border border-line bg-surface-card px-3 py-1 text-ink-secondary"
            }
          >
            {o.label}
          </button>
        ))}
      </div>

      {err && <div className="text-body3 text-status-error mb-2">{err}</div>}

      <div className="grid grid-cols-4 gap-3">
        {CARDS.map((c) => {
          const active = openKind === c.kind;
          return (
            <button
              key={c.key}
              type="button"
              onClick={() => drill(c.kind)}
              className={
                "rounded border px-3 py-4 text-left " +
                (active
                  ? "border-brand bg-brand/10"
                  : "border-line bg-surface-card hover:border-brand")
              }
            >
              <div className="text-sh1 text-ink-primary">{gaps ? gaps[c.key] : "-"}</div>
              <div className="text-body2 text-ink-primary mt-1">{c.label}</div>
              <div className="text-footnote text-ink-secondary mt-1">{c.hint}</div>
            </button>
          );
        })}
      </div>

      {openKind && (
        <div className="mt-3 rounded border border-line bg-surface-card px-3 py-3">
          <div className="text-body3 text-ink-secondary mb-2">
            {CARDS.find((c) => c.kind === openKind)?.label} · {rangeLabel(rangeKey)} · 最近 50 个会话
          </div>
          {drillLoading && <div className="text-body3 text-ink-secondary">加载中…</div>}
          {!drillLoading && drillRows.length === 0 && (
            <div className="text-body3 text-ink-secondary">暂无记录</div>
          )}
          {!drillLoading && drillRows.length > 0 && (
            <ul className="flex flex-col gap-1 text-body3">
              {drillRows.map((row) => (
                <li
                  key={row.conversation_id}
                  className="flex items-center gap-3 border-t border-line pt-1 first:border-t-0 first:pt-0"
                >
                  <Link
                    to={`/staff/conversations/${row.conversation_id}/logs`}
                    className="text-brand"
                  >
                    #{row.conversation_id}
                  </Link>
                  <span className="text-ink-secondary whitespace-nowrap">{row.last_at}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="mt-6">
        <h3 className="text-sh3 text-ink-primary mb-2">工具健康</h3>
        <table className="w-full text-body3">
          <thead>
            <tr className="text-ink-secondary text-left">
              <th className="py-1">工具</th>
              <th>调用数</th>
              <th>空结果数</th>
              <th>空结果率</th>
              <th>被拒数</th>
            </tr>
          </thead>
          <tbody>
            {tools.map((t) => {
              const hot = t.empty_rate > 0.5;
              return (
                <tr key={t.tool_name} className="border-t border-line text-ink-primary align-top">
                  <td className="py-1">{t.tool_name}</td>
                  <td>{t.calls}</td>
                  <td>{t.empty}</td>
                  <td className={hot ? "text-status-error" : undefined}>
                    {(t.empty_rate * 100).toFixed(0)}%
                  </td>
                  <td className={t.rejected > 0 ? "text-status-error" : undefined}>{t.rejected}</td>
                </tr>
              );
            })}
            {tools.length === 0 && !err && (
              <tr>
                <td colSpan={5} className="py-2 text-ink-secondary">
                  暂无记录
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="text-footnote text-ink-secondary mt-4">
        明细可在「全局工具审计」或具体会话的留痕页查看。
      </p>
    </div>
  );
}
