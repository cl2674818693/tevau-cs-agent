import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { getKpi, type StaffKpi } from "../../api/staff";
import { useStaffSession } from "../../hooks/useStaffSession";

function fmtDuration(seconds: number): string {
  if (seconds <= 0) return "-";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}分${s}秒` : `${s}秒`;
}

export function KpiRoute() {
  const { token } = useStaffSession();
  const nav = useNavigate();
  const [rows, setRows] = useState<StaffKpi[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) {
      nav("/staff/login");
      return;
    }
    getKpi(token)
      .then(setRows)
      .catch(() => setErr("加载失败"));
  }, [token, nav]);

  return (
    <div className="mx-auto max-w-[720px] px-page py-block-lg">
      <div className="flex items-center mb-3">
        <h2 className="text-sh2 text-ink-primary flex-1">客服 KPI 看板</h2>
        <Link to="/staff/conversations" className="text-body3 text-ink-secondary">
          返回工作台
        </Link>
      </div>
      {err && <div className="text-body3 text-status-error mb-2">{err}</div>}
      <table className="w-full text-body3">
        <thead>
          <tr className="text-ink-secondary text-left">
            <th className="py-1">客服</th>
            <th>接管</th>
            <th>解决</th>
            <th>释放回 AI</th>
            <th>解决率</th>
            <th>平均时长</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.staff_id} className="border-t border-line text-ink-primary">
              <td className="py-1">{r.staff_id}</td>
              <td>{r.takeovers}</td>
              <td>{r.resolved}</td>
              <td>{r.releases}</td>
              <td>{(r.resolved_ratio * 100).toFixed(0)}%</td>
              <td>{fmtDuration(r.avg_handle_seconds)}</td>
            </tr>
          ))}
          {rows.length === 0 && !err && (
            <tr>
              <td colSpan={6} className="py-2 text-ink-secondary">
                暂无数据
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
