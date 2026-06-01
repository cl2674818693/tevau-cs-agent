import {
  Alert,
  Card,
  Segmented,
  Skeleton,
  Table,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";

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
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title, Text } = Typography;

type RangeKey = "7d" | "30d" | "all";

const RANGE_OPTIONS: { value: RangeKey; label: string }[] = [
  { value: "7d", label: "近 7 天" },
  { value: "30d", label: "近 30 天" },
  { value: "all", label: "全部" },
];

function rangeOf(key: RangeKey): InsightsRange {
  if (key === "all") return {};
  const days = key === "7d" ? 7 : 30;
  const from = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
  return { from: from.toISOString().slice(0, 19).replace("T", " ") };
}

const CARDS: {
  key: keyof KnowledgeGaps;
  kind: GapKind;
  label: string;
  hint: string;
}[] = [
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
  {
    key: "thumbs_down",
    kind: "thumbs_down",
    label: "差评 👎",
    hint: "用户对 AI 回复点踩",
  },
  {
    key: "human_handoff",
    kind: "human_handoff",
    label: "转人工",
    hint: "会话从 AI 切换到人工接管",
  },
];

function DrillPanel({
  token,
  kind,
  rangeKey,
  label,
}: {
  token: string;
  kind: GapKind;
  rangeKey: RangeKey;
  label: string;
}) {
  const rangeLabel =
    RANGE_OPTIONS.find((o) => o.value === rangeKey)?.label ?? "";
  const { data, loading, error } = useAsyncData(
    () =>
      getGapConversations(token, kind, { ...rangeOf(rangeKey), limit: 50 }),
    [token, kind, rangeKey],
    "下钻加载失败",
  );
  const rows = data ?? [];

  const drillColumns: ColumnsType<GapConversation> = useMemo(
    () => [
      {
        title: "会话",
        dataIndex: "conversation_id",
        width: 120,
        render: (id: number) => (
          <Link
            to={`/staff/conversations/${id}/logs`}
            style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}
          >
            #{id}
          </Link>
        ),
      },
      {
        title: "最近时间",
        dataIndex: "last_at",
        render: (v: string) => (
          <span
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 12,
              color: "rgba(0,0,0,0.65)",
              whiteSpace: "nowrap",
            }}
          >
            {v}
          </span>
        ),
      },
    ],
    [],
  );

  return (
    <Card
      size="small"
      title={
        <Text type="secondary" style={{ fontSize: 13 }}>
          {label} · {rangeLabel} · 最近 50 个会话
        </Text>
      }
    >
      {error && (
        <Alert
          type="error"
          showIcon
          title={error}
          style={{ marginBottom: 12 }}
        />
      )}
      {loading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : (
        <Table<GapConversation>
          rowKey="conversation_id"
          size="small"
          columns={drillColumns}
          dataSource={rows}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          locale={{ emptyText: "暂无记录" }}
        />
      )}
    </Card>
  );
}

export function InsightsRoute() {
  const { token } = useStaffSession();
  const [rangeKey, setRangeKey] = useState<RangeKey>("7d");
  const [openKind, setOpenKind] = useState<GapKind | null>(null);

  const range = rangeOf(rangeKey);

  const {
    data: gapsAndTools,
    loading,
    error,
  } = useAsyncData(
    () =>
      token
        ? Promise.all([
            getKnowledgeGaps(token, range),
            getToolHealth(token, range),
          ])
        : null,
    [token, rangeKey],
    "加载失败",
  );

  const gaps = gapsAndTools?.[0] ?? null;
  const tools = gapsAndTools?.[1] ?? [];

  const drill = useCallback((kind: GapKind) => {
    setOpenKind((prev) => (prev === kind ? null : kind));
  }, []);

  const toolColumns: ColumnsType<ToolHealth> = useMemo(
    () => [
      {
        title: "工具",
        dataIndex: "tool_name",
        render: (v: string) => (
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
            {v}
          </span>
        ),
      },
      { title: "调用数", dataIndex: "calls", width: 100 },
      { title: "空结果数", dataIndex: "empty", width: 100 },
      {
        title: "空结果率",
        dataIndex: "empty_rate",
        width: 120,
        render: (v: number) => (
          <span
            style={{
              color: v > 0.5 ? "#dc2626" : undefined,
              fontWeight: v > 0.5 ? 600 : undefined,
            }}
          >
            {(v * 100).toFixed(0)}%
          </span>
        ),
      },
      {
        title: "被拒数",
        dataIndex: "rejected",
        width: 100,
        render: (v: number) => (
          <span
            style={{
              color: v > 0 ? "#dc2626" : undefined,
              fontWeight: v > 0 ? 600 : undefined,
            }}
          >
            {v}
          </span>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-4 p-6">
      <Title level={3} style={{ margin: 0 }}>
        知识缺口
      </Title>

      <Segmented
        value={rangeKey}
        onChange={(v) => {
          setRangeKey(v as RangeKey);
          setOpenKind(null);
        }}
        options={RANGE_OPTIONS}
      />

      {error && <Alert type="error" showIcon title={error} />}

      {loading ? (
        <Card>
          <Skeleton active paragraph={{ rows: 6 }} />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {CARDS.map((c) => {
              const active = openKind === c.kind;
              return (
                <Card
                  key={c.key}
                  hoverable
                  onClick={() => drill(c.kind)}
                  style={{
                    cursor: "pointer",
                    borderColor: active ? "#4f46e5" : undefined,
                    background: active ? "rgba(79, 70, 229, 0.05)" : undefined,
                  }}
                >
                  <div style={{ fontSize: 24, fontWeight: 600 }}>
                    {gaps ? gaps[c.key] : "-"}
                  </div>
                  <div style={{ marginTop: 4, fontSize: 14, fontWeight: 500 }}>
                    {c.label}
                  </div>
                  <Text
                    type="secondary"
                    style={{ marginTop: 4, fontSize: 12, display: "block" }}
                  >
                    {c.hint}
                  </Text>
                </Card>
              );
            })}
          </div>

          {openKind && token && (
            <DrillPanel
              token={token}
              kind={openKind}
              rangeKey={rangeKey}
              label={CARDS.find((c) => c.kind === openKind)?.label ?? ""}
            />
          )}

          <Card title="工具健康" size="small">
            <Table<ToolHealth>
              rowKey="tool_name"
              size="small"
              columns={toolColumns}
              dataSource={tools}
              pagination={false}
              locale={{ emptyText: "暂无记录" }}
            />
          </Card>
        </>
      )}

      <Text type="secondary" style={{ fontSize: 12 }}>
        明细可在「全局工具审计」或具体会话的留痕页查看。
      </Text>
    </div>
  );
}
