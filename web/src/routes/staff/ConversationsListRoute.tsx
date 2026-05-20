import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { listStaffConversations, type StaffConversation } from "../../api/staff";
import { useStaffSession } from "../../hooks/useStaffSession";

const FILTERS = ["human_pending", "human_takeover", "all"] as const;

export function ConversationsListRoute() {
  const { token, role, logout } = useStaffSession();
  const canSpectate = role === "senior" || role === "engineer";
  const [status, setStatus] = useState<string>("human_pending");
  const [items, setItems] = useState<StaffConversation[]>([]);
  const [err, setErr] = useState("");
  const nav = useNavigate();

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    listStaffConversations(token, status)
      .then(setItems)
      .catch(() => setErr("加载失败，请重新登录"));
  }, [token, status, nav]);

  return (
    <div className="mx-auto max-w-[720px] px-page py-block-lg">
      <div className="flex items-center mb-3">
        <h2 className="text-sh2 text-ink-primary flex-1">客服工作台</h2>
        <Link to="/staff/kpi" className="text-body3 text-ink-secondary mr-3">
          KPI
        </Link>
        <button onClick={logout} className="text-body3 text-ink-secondary">
          退出
        </button>
      </div>
      <div className="flex gap-2 mb-3">
        {FILTERS.map((f) => (
          <button
            key={f}
            onClick={() => setStatus(f)}
            className={`text-body3 px-2 py-1 rounded ${
              status === f ? "bg-brand text-ink-primary" : "bg-surface-container text-ink-secondary"
            }`}
          >
            {f}
          </button>
        ))}
      </div>
      {err && <div className="text-body3 text-status-error">{err}</div>}
      <ul className="flex flex-col gap-2">
        {items.map((c) => (
          <li key={c.id} className="flex items-center gap-2">
            <Link
              to={`/staff/conversations/${c.id}`}
              className="block flex-1 rounded border border-line bg-surface-card px-3 py-2"
            >
              <span className="text-body1 text-ink-primary">
                #{c.id} · {c.user_type === "c" ? "C 端用户" : "BU"} {c.subject_id}
              </span>
              <span className="ml-2 text-body3 text-ink-secondary">{c.mode}</span>
            </Link>
            {canSpectate && (
              <Link
                to={`/staff/conversations/${c.id}/spectate`}
                className="text-body3 text-ink-secondary px-2 py-1 rounded bg-surface-container"
              >
                旁观
              </Link>
            )}
          </li>
        ))}
        {items.length === 0 && !err && <li className="text-body3 text-ink-secondary">暂无会话</li>}
      </ul>
    </div>
  );
}
