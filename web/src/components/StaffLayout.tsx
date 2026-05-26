import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";

import { useStaffSession } from "../hooks/useStaffSession";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";

const NAV_ITEMS: { to: string; label: string; adminOnly?: boolean }[] = [
  { to: "/staff/conversations", label: "工作台" },
  { to: "/staff/tickets", label: "工单" },
  { to: "/staff/kpi", label: "KPI" },
  { to: "/staff/insights", label: "知识缺口" },
  { to: "/staff/audits", label: "工具审计" },
  { to: "/admin/prompts", label: "Prompt 灰度", adminOnly: true },
];

function StaffSidebar() {
  const { role, logout } = useStaffSession();
  const nav = useNavigate();
  return (
    <aside className="flex w-[220px] shrink-0 flex-col border-r border-line bg-surface-card">
      <div className="px-4 py-4 text-sh2 text-ink-primary">◉ CS</div>
      <nav className="flex flex-1 flex-col gap-1 px-2">
        {NAV_ITEMS.filter((i) => !i.adminOnly || role === "admin").map((i) => (
          <NavLink
            key={i.to}
            to={i.to}
            className={({ isActive }) =>
              cn(
                "rounded-md px-3 py-2 text-body2 transition-colors",
                isActive
                  ? "bg-brand text-ink-onbrand"
                  : "text-ink-secondary hover:bg-surface-hover hover:text-ink-primary",
              )
            }
          >
            {i.label}
          </NavLink>
        ))}
      </nav>
      <div className="flex flex-col gap-2 border-t border-line px-3 py-3">
        {role && <span className="text-footnote text-ink-secondary">角色：{role}</span>}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            logout();
            nav("/staff/login");
          }}
        >
          退出
        </Button>
      </div>
    </aside>
  );
}

export function StaffLayout() {
  const { token } = useStaffSession();
  if (!token) return <Navigate to="/staff/login" replace />;
  return (
    <div className="flex h-screen">
      <StaffSidebar />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
