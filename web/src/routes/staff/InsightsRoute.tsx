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
import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { EmptyState } from "../../components/ui/empty-state";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { Table, TableScroll, TBody, Td, Th, THead, Tr } from "../../components/ui/table";
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
  const [loading, setLoading] = useState(true);

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
    setLoading(true);
    Promise.all([getKnowledgeGaps(token, range), getToolHealth(token, range)])
      .then(([g, t]) => {
        setGaps(g);
        setTools(t);
        setErr("");
      })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
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
    <PageContainer width="wide">
      <PageHeader title="知识缺口报表" />

      <div className="mb-3 flex items-center gap-2 text-body3">
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

      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}

      {loading ? (
        <LoadingState />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
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
                  <div className="mt-1 text-body2 text-ink-primary">{c.label}</div>
                  <div className="mt-1 text-footnote text-ink-secondary">{c.hint}</div>
                </button>
              );
            })}
          </div>

          {openKind && (
            <Card className="mt-3 px-3 py-3">
              <div className="mb-2 text-body3 text-ink-secondary">
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
                      <span className="whitespace-nowrap text-ink-secondary">{row.last_at}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          <div className="mt-6">
            <h3 className="mb-2 text-sh3 text-ink-primary">工具健康</h3>
            {tools.length === 0 ? (
              <EmptyState>暂无记录</EmptyState>
            ) : (
              <TableScroll>
                <Table className="min-w-[480px]">
                  <THead>
                    <tr>
                      <Th>工具</Th>
                      <Th>调用数</Th>
                      <Th>空结果数</Th>
                      <Th>空结果率</Th>
                      <Th>被拒数</Th>
                    </tr>
                  </THead>
                  <TBody>
                    {tools.map((t) => {
                      const hot = t.empty_rate > 0.5;
                      return (
                        <Tr key={t.tool_name} className="align-top">
                          <Td>{t.tool_name}</Td>
                          <Td>{t.calls}</Td>
                          <Td>{t.empty}</Td>
                          <Td className={hot ? "text-status-error" : undefined}>
                            {(t.empty_rate * 100).toFixed(0)}%
                          </Td>
                          <Td className={t.rejected > 0 ? "text-status-error" : undefined}>
                            {t.rejected}
                          </Td>
                        </Tr>
                      );
                    })}
                  </TBody>
                </Table>
              </TableScroll>
            )}
          </div>
        </>
      )}

      <p className="mt-4 text-footnote text-ink-secondary">
        明细可在「全局工具审计」或具体会话的留痕页查看。
      </p>
    </PageContainer>
  );
}
