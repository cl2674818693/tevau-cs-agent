import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getRecentAudits, type ToolAudit } from "../../api/staff";
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
    getRecentAudits(token, filter())
      .then((data) => {
        setRows(data);
        setHasMore(data.length >= 100);
      })
      .catch(() => setErr("加载失败"));
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
    <div className="mx-auto max-w-[860px] px-page py-block-lg">
      <div className="flex items-center mb-3">
        <h2 className="text-sh2 text-ink-primary flex-1">全局工具审计</h2>
        <Link to="/staff/conversations" className="text-body3 text-ink-secondary">
          返回工作台
        </Link>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-body3 text-ink-secondary mb-3">
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
      {err && <div className="text-body3 text-status-error mb-2">{err}</div>}
      <table className="w-full text-body3">
        <thead>
          <tr className="text-ink-secondary text-left">
            <th className="py-1">时间</th>
            <th>会话</th>
            <th>工具</th>
            <th>身份</th>
            <th>返回</th>
            <th>耗时</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => (
            <tr key={a.id} className="border-t border-line text-ink-primary align-top">
              <td className="py-1 whitespace-nowrap">{a.created_at}</td>
              <td>
                <Link to={`/staff/conversations/${a.conversation_id}/logs`} className="text-brand">
                  #{a.conversation_id}
                </Link>
              </td>
              <td>{a.tool_name}</td>
              <td className="text-ink-secondary whitespace-nowrap">
                {a.user_type ?? "-"}
                {a.subject_id ? `:${a.subject_id}` : ""}
              </td>
              <td className={isEmpty(a) ? "text-status-error" : undefined}>
                {a.result_count ?? 0} 条
              </td>
              <td>{a.duration_ms}ms</td>
              <td>
                {a.rejected ? (
                  <span className="text-status-error">被拒：{a.reject_reason ?? "-"}</span>
                ) : (
                  <span className="text-ink-secondary">ok</span>
                )}
              </td>
            </tr>
          ))}
          {rows.length === 0 && !err && (
            <tr>
              <td colSpan={7} className="py-2 text-ink-secondary">
                暂无记录
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {hasMore && rows.length > 0 && (
        <button
          type="button"
          onClick={loadMore}
          className="mt-3 rounded border border-line px-3 py-1 text-body3 text-ink-secondary"
        >
          加载更多
        </button>
      )}
    </div>
  );
}
