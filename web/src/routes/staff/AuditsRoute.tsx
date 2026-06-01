import {
  Alert,
  Button,
  Card,
  Input,
  Select,
  Skeleton,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getRecentAudits } from "../../api/staff";
import type { ToolAudit } from "../../api/staff";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title } = Typography;

const PAGE_SIZE = 100;

const TOOL_OPTIONS = [
  "query_user",
  "query_card",
  "query_kyc",
  "query_balance",
  "query_transaction",
  "query_bu_order",
  "query_bu_request_log",
  "create_ticket",
  "search_code",
  "lookup_api_doc",
  "read_file",
];

function isEmpty(a: ToolAudit): boolean {
  return a.is_empty === 1 || a.is_empty === true;
}

export function AuditsRoute() {
  const { token } = useStaffSession();

  const [rejectedOnly, setRejectedOnly] = useState(false);
  const [emptyOnly, setEmptyOnly] = useState(false);
  const [toolName, setToolName] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [page, setPage] = useState(1);

  function onFilter<T>(setter: (v: T) => void) {
    return (v: T) => {
      setter(v);
      setPage(1);
    };
  }

  const filter = useMemo(
    () => ({
      rejectedOnly,
      emptyOnly,
      toolName: toolName || undefined,
      conversationId: conversationId.trim() || undefined,
      page,
      limit: PAGE_SIZE,
    }),
    [rejectedOnly, emptyOnly, toolName, conversationId, page],
  );

  const { data, loading, error } = useAsyncData(
    () => (token ? getRecentAudits(token, filter) : null),
    [token, filter],
    "加载失败",
  );

  const rows = data?.audits ?? [];
  const total = data?.total ?? 0;

  const columns: ColumnsType<ToolAudit> = useMemo(
    () => [
      {
        title: "时间",
        dataIndex: "created_at",
        width: 180,
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
      {
        title: "会话",
        dataIndex: "conversation_id",
        width: 100,
        render: (id: number | null) =>
          id != null ? (
            <Link
              to={`/staff/conversations/${id}/logs`}
              style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}
            >
              #{id}
            </Link>
          ) : (
            <span style={{ color: "rgba(0,0,0,0.45)" }}>—</span>
          ),
      },
      {
        title: "工具",
        dataIndex: "tool_name",
        render: (v: string) => (
          <span
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 12,
              whiteSpace: "nowrap",
            }}
          >
            {v}
          </span>
        ),
      },
      {
        title: "身份",
        key: "identity",
        render: (_: unknown, row: ToolAudit) => (
          <span
            style={{
              fontFamily: "ui-monospace, monospace",
              fontSize: 12,
              color: "rgba(0,0,0,0.65)",
              whiteSpace: "nowrap",
            }}
          >
            {row.user_type ?? "-"}
            {row.subject_id ? `:${row.subject_id}` : ""}
          </span>
        ),
      },
      {
        title: "返回",
        dataIndex: "result_count",
        width: 100,
        render: (_: unknown, row: ToolAudit) => (
          <span style={{ color: isEmpty(row) ? "#dc2626" : undefined }}>
            {row.result_count ?? 0} 条
          </span>
        ),
      },
      {
        title: "耗时",
        dataIndex: "duration_ms",
        width: 100,
        render: (v: number) => (
          <span style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
            {v}ms
          </span>
        ),
      },
      {
        title: "状态",
        dataIndex: "rejected",
        width: 140,
        render: (_: unknown, row: ToolAudit) =>
          row.rejected ? (
            <Tag color="red">被拒：{row.reject_reason ?? "-"}</Tag>
          ) : (
            <Tag color="green">ok</Tag>
          ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-4 p-6">
      <Title level={3} style={{ margin: 0 }}>
        工具审计
      </Title>

      <Card>
        <Space wrap style={{ marginBottom: 12 }}>
          <Select
            value={toolName}
            onChange={onFilter(setToolName)}
            style={{ width: 200 }}
            options={[
              { value: "", label: "全部工具" },
              ...TOOL_OPTIONS.map((t) => ({ value: t, label: t })),
            ]}
          />
          <Input
            placeholder="会话号"
            inputMode="numeric"
            value={conversationId}
            onChange={(e) => onFilter(setConversationId)(e.target.value)}
            style={{ width: 120 }}
            allowClear
          />
          <Button
            type={rejectedOnly ? "primary" : "default"}
            size="small"
            onClick={() => onFilter(setRejectedOnly)(!rejectedOnly)}
          >
            只看被拒
          </Button>
          <Button
            type={emptyOnly ? "primary" : "default"}
            size="small"
            onClick={() => onFilter(setEmptyOnly)(!emptyOnly)}
          >
            只看空结果
          </Button>
        </Space>

        {error && (
          <Alert
            type="error"
            showIcon
            title={error}
            style={{ marginBottom: 12 }}
          />
        )}

        {loading ? (
          <Skeleton active paragraph={{ rows: 8 }} />
        ) : (
          <Table<ToolAudit>
            rowKey={(r) => `${r.created_at}-${r.tool_name}-${r.conversation_id ?? ""}`}
            size="small"
            columns={columns}
            dataSource={rows}
            pagination={{
              current: page,
              pageSize: PAGE_SIZE,
              total,
              onChange: setPage,
              showSizeChanger: false,
            }}
            locale={{ emptyText: "暂无记录" }}
            scroll={{ x: "max-content" }}
          />
        )}
      </Card>
    </div>
  );
}
