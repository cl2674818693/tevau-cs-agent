import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { listTickets, type Ticket, type TicketStatus } from "../../api/staff";
import { useStaffSession } from "../../hooks/useStaffSession";

const PAGE_SIZE = 50;
const SEVERITY_OPTIONS = ["p0", "p1", "p2", "p3"];

// 工单状态 -> 标签 + 颜色（外部事项中心事件驱动；pending=已建单未受理）
const STATUS_META: Record<TicketStatus, { label: string; className: string }> = {
  pending: { label: "待处理", className: "text-status-warning" },
  in_progress: { label: "进行中", className: "text-status-success" },
  resolved: { label: "已解决", className: "text-brand" },
  closed: { label: "已关闭", className: "text-ink-secondary" },
};

function TicketStatusCell({ status }: { status: TicketStatus }) {
  const meta = STATUS_META[status] ?? STATUS_META.in_progress;
  return <span className={meta.className}>{meta.label}</span>;
}

// eslint-disable-next-line max-lines-per-function -- 工单列表页：筛选区 + 表格 + 分页
export function TicketsRoute() {
  const { token } = useStaffSession();
  const nav = useNavigate();
  const [openOnly, setOpenOnly] = useState(true);
  const [severity, setSeverity] = useState("");
  const [rows, setRows] = useState<Ticket[]>([]);
  const [err, setErr] = useState("");
  const [hasMore, setHasMore] = useState(false);

  const filter = useCallback(
    (beforeId?: string) => ({
      open: openOnly,
      severity: severity || undefined,
      beforeId,
      limit: PAGE_SIZE,
    }),
    [openOnly, severity],
  );

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    listTickets(token, filter())
      .then((data) => {
        setRows(data);
        setHasMore(data.length >= PAGE_SIZE);
        setErr("");
      })
      .catch(() => setErr("加载失败"));
  }, [token, filter, nav]);

  const loadMore = () => {
    if (!token || rows.length === 0) return;
    const lastId = rows[rows.length - 1].external_id;
    listTickets(token, filter(lastId))
      .then((data) => {
        setRows((prev) => [...prev, ...data]);
        setHasMore(data.length >= PAGE_SIZE);
      })
      .catch(() => setErr("加载失败"));
  };

  return (
    <div className="mx-auto max-w-[860px] px-page py-block-lg">
      <div className="flex items-center mb-3">
        <h2 className="text-sh2 text-ink-primary flex-1">工单列表</h2>
        <Link to="/staff/conversations" className="text-body3 text-ink-secondary">
          返回工作台
        </Link>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-body3 text-ink-secondary mb-3">
        <select
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          className="rounded border border-line bg-surface-card px-2 py-1 text-ink-primary"
        >
          <option value="">全部严重度</option>
          {SEVERITY_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={openOnly}
            onChange={(e) => setOpenOnly(e.target.checked)}
          />
          只看未关闭
        </label>
      </div>
      {err && <div className="text-body3 text-status-error mb-2">{err}</div>}
      <table className="w-full text-body3">
        <thead>
          <tr className="text-ink-secondary text-left">
            <th className="py-1">工单号</th>
            <th>分类</th>
            <th>严重度</th>
            <th>状态</th>
            <th>时间</th>
            <th>会话</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.external_id} className="border-t border-line text-ink-primary align-top">
              <td className="py-1 whitespace-nowrap">
                <Link to={`/staff/tickets/${t.external_id}`} className="text-brand">
                  {t.external_id}
                </Link>
              </td>
              <td>{t.category ?? "-"}</td>
              <td>{t.severity ?? "-"}</td>
              <td>
                <TicketStatusCell status={t.status} />
              </td>
              <td className="whitespace-nowrap">{t.created_at}</td>
              <td>
                <Link
                  to={`/staff/conversations/${t.conversation_id}/logs`}
                  className="text-brand"
                >
                  #{t.conversation_id}
                </Link>
              </td>
            </tr>
          ))}
          {rows.length === 0 && !err && (
            <tr>
              <td colSpan={6} className="py-2 text-ink-secondary">
                暂无工单
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
