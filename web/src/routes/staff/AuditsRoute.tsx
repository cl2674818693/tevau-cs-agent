import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getRecentAudits } from "../../api/staff";
import type { ToolAudit } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { EmptyState } from "../../components/ui/empty-state";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { Table, TableScroll, TBody, Td, Th, THead, Tr } from "../../components/ui/table";
import { useStaffSession } from "../../hooks/useStaffSession";

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

// eslint-disable-next-line max-lines-per-function -- 审计页：筛选区 + 表格 + 分页
export function AuditsRoute() {
  const { token } = useStaffSession();
  const nav = useNavigate();
  const [rejectedOnly, setRejectedOnly] = useState(false);
  const [emptyOnly, setEmptyOnly] = useState(false);
  const [toolName, setToolName] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [rows, setRows] = useState<ToolAudit[]>([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(false);

  const filter = useCallback(
    (beforeId?: number) => ({
      rejectedOnly,
      emptyOnly,
      toolName: toolName || undefined,
      conversationId: conversationId.trim() || undefined,
      beforeId,
    }),
    [rejectedOnly, emptyOnly, toolName, conversationId],
  );

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    setLoading(true);
    setErr("");
    getRecentAudits(token, filter())
      .then((data) => {
        setRows(data);
        setHasMore(data.length >= 100);
      })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }, [token, filter, nav]);

  const loadMore = () => {
    if (!token || rows.length === 0) return;
    const lastId = rows[rows.length - 1].id;
    getRecentAudits(token, filter(lastId))
      .then((data) => {
        setRows((prev) => [...prev, ...data]);
        setHasMore(data.length >= 100);
      })
      .catch(() => setErr("加载失败"));
  };

  return (
    <PageContainer width="wide">
      <PageHeader title="全局工具审计" />
      <div className="mb-3 flex flex-wrap items-center gap-3 text-body3 text-ink-secondary">
        <select
          value={toolName}
          onChange={(e) => setToolName(e.target.value)}
          className="rounded border border-line bg-surface-card px-2 py-1 text-ink-primary"
        >
          <option value="">全部工具</option>
          {TOOL_OPTIONS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          type="text"
          inputMode="numeric"
          placeholder="会话号"
          value={conversationId}
          onChange={(e) => setConversationId(e.target.value)}
          className="w-24 rounded border border-line bg-surface-card px-2 py-1 text-ink-primary"
        />
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={rejectedOnly}
            onChange={(e) => setRejectedOnly(e.target.checked)}
          />
          只看被拒
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={emptyOnly}
            onChange={(e) => setEmptyOnly(e.target.checked)}
          />
          只看空结果
        </label>
      </div>
      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}
      {loading ? (
        <LoadingState />
      ) : rows.length === 0 ? (
        <EmptyState>暂无记录</EmptyState>
      ) : (
        <TableScroll>
          <Table className="min-w-[720px]">
            <THead>
              <tr>
                <Th>时间</Th>
                <Th>会话</Th>
                <Th>工具</Th>
                <Th>身份</Th>
                <Th>返回</Th>
                <Th>耗时</Th>
                <Th>状态</Th>
              </tr>
            </THead>
            <TBody>
              {rows.map((a) => (
                <Tr key={a.id} className="align-top">
                  <Td className="whitespace-nowrap">{a.created_at}</Td>
                  <Td>
                    <Link
                      to={`/staff/conversations/${a.conversation_id}/logs`}
                      className="text-brand"
                    >
                      #{a.conversation_id}
                    </Link>
                  </Td>
                  <Td className="whitespace-nowrap">{a.tool_name}</Td>
                  <Td className="whitespace-nowrap text-ink-secondary">
                    {a.user_type ?? "-"}
                    {a.subject_id ? `:${a.subject_id}` : ""}
                  </Td>
                  <Td className={isEmpty(a) ? "text-status-error" : undefined}>
                    {a.result_count ?? 0} 条
                  </Td>
                  <Td className="whitespace-nowrap">{a.duration_ms}ms</Td>
                  <Td>
                    {a.rejected ? (
                      <Badge variant="error">被拒：{a.reject_reason ?? "-"}</Badge>
                    ) : (
                      <Badge variant="success">ok</Badge>
                    )}
                  </Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        </TableScroll>
      )}
      {hasMore && rows.length > 0 && (
        <button
          type="button"
          onClick={loadMore}
          className="mt-3 rounded border border-line px-3 py-1 text-body3 text-ink-secondary"
        >
          加载更多
        </button>
      )}
    </PageContainer>
  );
}
