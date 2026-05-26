import { useEffect, useMemo, useState } from "react";

import { getKpi, type AiQuality, type StaffKpi } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { Card, CardContent } from "../../components/ui/card";
import { EmptyState } from "../../components/ui/empty-state";
import { FilterTabs } from "../../components/ui/filter-tabs";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Table, TBody, Td, Th, THead, Tr } from "../../components/ui/table";
import { useStaffSession } from "../../hooks/useStaffSession";

function fmtDuration(seconds: number): string {
  if (seconds <= 0) return "-";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}分${s}秒` : `${s}秒`;
}

function pct(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`;
}

// 后端按 created_at 字符串字典序比较，from 必须是 "YYYY-MM-DD HH:MM:SS"（UTC，无 T 无 Z）
function utcFrom(daysAgo: number): string {
  const d = new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000);
  return d.toISOString().slice(0, 19).replace("T", " ");
}

type RangeKey = "7d" | "30d" | "all";

const RANGE_OPTIONS: { value: RangeKey; label: string }[] = [
  { value: "7d", label: "近7天" },
  { value: "30d", label: "近30天" },
  { value: "all", label: "全部" },
];

function QualityMetric({
  label,
  value,
  hint,
  alert,
}: {
  label: string;
  value: string;
  hint?: string;
  alert?: boolean;
}) {
  return (
    <Card>
      <CardContent>
        <div className="text-footnote text-ink-secondary">{label}</div>
        <div className={alert ? "text-sh2 text-status-error" : "text-sh2 text-ink-primary"}>
          {value}
        </div>
        {hint && <div className="text-footnote text-ink-footnote mt-0.5">{hint}</div>}
      </CardContent>
    </Card>
  );
}

export function KpiRoute() {
  const { token } = useStaffSession();
  const [range, setRange] = useState<RangeKey>("7d");
  const [rows, setRows] = useState<StaffKpi[]>([]);
  const [quality, setQuality] = useState<AiQuality | null>(null);
  const [err, setErr] = useState("");

  const from = useMemo(() => {
    if (range === "7d") return utcFrom(7);
    if (range === "30d") return utcFrom(30);
    return undefined;
  }, [range]);

  useEffect(() => {
    if (!token) return;
    setErr("");
    getKpi(token, { from })
      .then((res) => {
        setRows(res.staff);
        setQuality(res.ai_quality);
      })
      .catch(() => setErr("加载失败"));
  }, [token, from]);

  return (
    <PageContainer>
      <PageHeader title="客服 KPI 看板" />
      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}

      <FilterTabs value={range} onChange={setRange} options={RANGE_OPTIONS} className="mb-4" />

      {quality && (
        <div className="mb-6">
          <h2 className="text-sh2 text-ink-primary mb-2">AI 质量</h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <QualityMetric
              label="转人工率"
              value={pct(quality.handoff_rate)}
              hint={`${quality.handoff} / ${quality.total_conversations} 会话`}
              alert={quality.handoff_rate > 0.5}
            />
            <QualityMetric
              label="差评率"
              value={pct(quality.downvote_rate)}
              hint={`${quality.downvote} / ${quality.downvote + quality.upvote} 有反馈消息`}
              alert={quality.downvote_rate > 0.2}
            />
            <QualityMetric
              label="工具空结果率"
              value={pct(quality.tool_empty_rate)}
              hint={`${quality.tool_empty} / ${quality.tool_calls} 工具调用`}
              alert={quality.tool_empty_rate > 0.3}
            />
            <QualityMetric
              label="范围外提问"
              value={String(quality.out_of_scope)}
              hint="计数"
            />
            <QualityMetric label="失败回合" value={String(quality.failed_turns)} hint="计数" />
          </div>
        </div>
      )}

      <h2 className="text-sh2 text-ink-primary mb-2">客服明细</h2>
      <Table>
        <THead>
          <tr>
            <Th>客服</Th>
            <Th>接管</Th>
            <Th>解决</Th>
            <Th>释放回 AI</Th>
            <Th>转交</Th>
            <Th>转交率</Th>
            <Th>释放率</Th>
            <Th>解决率</Th>
            <Th>平均时长</Th>
          </tr>
        </THead>
        <TBody>
          {rows.map((r) => (
            <Tr key={r.staff_id}>
              <Td>{r.staff_id}</Td>
              <Td>{r.takeovers}</Td>
              <Td>{r.resolved}</Td>
              <Td>{r.releases}</Td>
              <Td>{r.transfers ?? 0}</Td>
              <Td>{r.transfer_ratio != null ? `${(r.transfer_ratio * 100).toFixed(0)}%` : "-"}</Td>
              <Td>{(r.release_ratio * 100).toFixed(0)}%</Td>
              <Td>{(r.resolved_ratio * 100).toFixed(0)}%</Td>
              <Td>{fmtDuration(r.avg_handle_seconds)}</Td>
            </Tr>
          ))}
        </TBody>
      </Table>
      {rows.length === 0 && !err && <EmptyState>暂无数据</EmptyState>}
    </PageContainer>
  );
}
