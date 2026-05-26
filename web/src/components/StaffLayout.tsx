import {
  BarChart3,
  ChevronLeft,
  Inbox,
  Lightbulb,
  type LucideIcon,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { useStaffSession } from "../hooks/useStaffSession";
import { cn } from "../lib/utils";
import { Button } from "./ui/button";

type NavItem = {
  to: string;
  label: string;
  /** 移动端底部 Tab 用的短标签（避免长标签折行），缺省回退 label。 */
  short?: string;
  icon: LucideIcon;
  adminOnly?: boolean;
};

const NAV_ITEMS: NavItem[] = [
  { to: "/staff/conversations", label: "工单", icon: Inbox },
  { to: "/staff/kpi", label: "KPI", icon: BarChart3 },
  { to: "/staff/insights", label: "知识缺口", short: "缺口", icon: Lightbulb },
  { to: "/staff/audits", label: "工具审计", short: "审计", icon: ShieldCheck },
  { to: "/admin/prompts", label: "Prompt 灰度", short: "灰度", icon: SlidersHorizontal, adminOnly: true },
];

function useNavItems() {
  const { role } = useStaffSession();
  return NAV_ITEMS.filter((i) => !i.adminOnly || role === "admin");
}

/** 桌面端固定侧栏（md 及以上）。 */
function Sidebar() {
  const items = useNavItems();
  const { role, logout } = useStaffSession();
  const nav = useNavigate();
  return (
    <aside className="hidden w-[220px] shrink-0 flex-col border-r border-line bg-surface-card md:flex">
      <div className="px-4 py-4 text-sh2 text-ink-primary">◉ CS 工作台</div>
      <nav className="flex flex-1 flex-col gap-1 px-2">
        {items.map((i) => (
          <NavLink
            key={i.to}
            to={i.to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-body2 transition-colors",
                isActive
                  ? "bg-brand text-ink-onbrand"
                  : "text-ink-secondary hover:bg-surface-hover hover:text-ink-primary",
              )
            }
          >
            <i.icon className="h-4 w-4 shrink-0" aria-hidden />
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

/** 移动端顶部细条（md 以下）：顶级页显示品牌+退出，下钻页显示返回。 */
function MobileTopBar({ isTopLevel }: { isTopLevel: boolean }) {
  const { role, logout } = useStaffSession();
  const nav = useNavigate();
  return (
    <header className="safe-top flex shrink-0 items-center gap-2 border-b border-line bg-surface-card px-3 pb-2 md:hidden">
      {isTopLevel ? (
        <span className="flex-1 text-sh2 text-ink-primary">◉ CS 工作台</span>
      ) : (
        <button
          onClick={() => nav(-1)}
          className="flex flex-1 items-center gap-1 text-body2 text-ink-secondary"
          aria-label="返回"
        >
          <ChevronLeft className="h-5 w-5" aria-hidden />
          返回
        </button>
      )}
      {role && <span className="text-footnote text-ink-secondary">{role}</span>}
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
    </header>
  );
}

/** 移动端底部 Tab 栏（md 以下）：顶级导航，下钻页隐藏以让位输入框。 */
function MobileTabBar() {
  const items = useNavItems();
  return (
    <nav className="safe-bottom flex shrink-0 items-stretch border-t border-line bg-surface-card md:hidden">
      {items.map((i) => (
        <NavLink
          key={i.to}
          to={i.to}
          className={({ isActive }) =>
            cn(
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-footnote whitespace-nowrap transition-colors",
              isActive ? "text-brand" : "text-ink-secondary",
            )
          }
        >
          <i.icon className="h-5 w-5" aria-hidden />
          {i.short ?? i.label}
        </NavLink>
      ))}
    </nav>
  );
}

export function StaffLayout() {
  const { token } = useStaffSession();
  const { pathname } = useLocation();
  if (!token) return <Navigate to="/staff/login" replace />;

  const isTopLevel = NAV_ITEMS.some((i) => i.to === pathname);
  // 会话详情（接管页）底部有输入框，隐藏底 Tab 避免重叠。
  const isConversationDetail = /^\/staff\/conversations\/\d+$/.test(pathname);

  return (
    <div className="flex h-screen flex-col md:flex-row">
      <Sidebar />
      <MobileTopBar isTopLevel={isTopLevel} />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
      {!isConversationDetail && <MobileTabBar />}
    </div>
  );
}
