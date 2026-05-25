import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getRecentAudits, type ToolAudit } from "../../api/staff";
import { useStaffSession } from "../../hooks/useStaffSession";

export function AuditsRoute() {
  const { token } = useStaffSession();
  const nav = useNavigate();
  const [rejectedOnly, setRejectedOnly] = useState(false);
  const [rows, setRows] = useState<ToolAudit[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    getRecentAudits(token, rejectedOnly)
      .then(setRows)
      .catch(() => setErr("加载失败"));
  }, [token, rejectedOnly, nav]);

  return (
    <div className="mx-auto max-w-[860px] px-page py-block-lg">
      <div className="flex items-center mb-3">
        <h2 className="text-sh2 text-ink-primary flex-1">全局工具审计</h2>
        <Link to="/staff/conversations" className="text-body3 text-ink-secondary">
          返回工作台
        </Link>
      </div>
      <label className="flex items-center gap-2 text-body3 text-ink-secondary mb-3">
        <input
          type="checkbox"
          checked={rejectedOnly}
          onChange={(e) => setRejectedOnly(e.target.checked)}
        />
        只看被拒
      </label>
      {err && <div className="text-body3 text-status-error mb-2">{err}</div>}
      <table className="w-full text-body3">
        <thead>
          <tr className="text-ink-secondary text-left">
            <th className="py-1">时间</th>
            <th>会话</th>
            <th>工具</th>
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
              <td colSpan={5} className="py-2 text-ink-secondary">
                暂无记录
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
