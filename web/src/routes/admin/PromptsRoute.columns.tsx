import { EditOutlined } from "@ant-design/icons";
import { Button, Progress, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { PromptAbStat } from "../../api/admin";

export type PromptRow = {
  version: string;
  rollout: number;
  isDefault: boolean;
  stat: PromptAbStat | undefined;
};

function AbStatsCell({ s }: { s: PromptAbStat | undefined }) {
  if (!s)
    return (
      <span style={{ color: "rgba(0,0,0,0.45)", fontSize: 12 }}>—</span>
    );
  const failHigh = s.failed_rate > 0.1;
  const dvHigh = s.downvote_rate > 0.2;
  return (
    <div className="flex items-center gap-3" style={{ fontSize: 12 }}>
      <span style={{ color: "rgba(0,0,0,0.45)" }}>{s.assistant_turns} 轮</span>
      <span style={{ color: failHigh ? "#dc2626" : "rgba(0,0,0,0.45)" }}>
        失败 {(s.failed_rate * 100).toFixed(1)}%
      </span>
      <span style={{ color: dvHigh ? "#dc2626" : "rgba(0,0,0,0.45)" }}>
        差评 {(s.downvote_rate * 100).toFixed(1)}%
      </span>
    </div>
  );
}

export function buildPromptColumns(
  onEdit: (row: PromptRow) => void,
): ColumnsType<PromptRow> {
  return [
    {
      title: "版本",
      dataIndex: "version",
      sorter: (a, b) => a.version.localeCompare(b.version),
      render: (v: string) => (
        <span style={{ fontFamily: "ui-monospace, monospace" }}>{v}</span>
      ),
    },
    {
      title: "角色",
      dataIndex: "isDefault",
      width: 100,
      render: (isDefault: boolean) =>
        isDefault ? (
          <Tag color="blue">default</Tag>
        ) : (
          <Tag>灰度</Tag>
        ),
    },
    {
      title: "流量",
      dataIndex: "rollout",
      width: 180,
      render: (pct: number) => (
        <div className="flex items-center gap-2">
          <Progress
            percent={Math.min(pct, 100)}
            showInfo={false}
            size="small"
            style={{ width: 100, marginBottom: 0 }}
          />
          <span style={{ fontVariantNumeric: "tabular-nums", fontSize: 13 }}>
            {pct}%
          </span>
        </div>
      ),
    },
    {
      title: "A/B 表现",
      key: "ab_stats",
      render: (_: unknown, row: PromptRow) => <AbStatsCell s={row.stat} />,
    },
    {
      title: "",
      key: "actions",
      width: 120,
      align: "right",
      render: (_: unknown, row: PromptRow) => (
        <Button
          type="text"
          size="small"
          icon={<EditOutlined />}
          onClick={() => onEdit(row)}
        >
          调整流量
        </Button>
      ),
    },
  ];
}
