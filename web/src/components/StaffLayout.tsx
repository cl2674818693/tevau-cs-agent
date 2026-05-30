import {
  BarChart3,
  ChevronLeft,
  ClipboardCheck,
  Inbox,
  KeySquare,
  LayoutDashboard,
  Lightbulb,
  type LucideIcon,
  ScrollText,
  Shield,
  ShieldCheck,
  SlidersHorizontal,
  Ticket,
  Timer,
  UserCog,
  Users,
  Wallet,
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
  /** 允许访问该菜单项的角色列表；缺省表示所有已登录用户可见。 */
  roles?: string[];
};

const NAV_ITEMS: NavItem[] = [
  { to: "/staff/conversations", label: "工作台", short: "工作台", icon: Inbox },
  { to: "/staff/tickets", label: "工单", icon: Ticket },
  { to: "/staff/kpi", label: "KPI", icon: BarChart3 },
  { to: "/staff/insights", label: "知识缺口", short: "缺口", icon: Lightbulb },
  { to: "/staff/audits", label: "工具审计", short: "审计", icon: ShieldCheck },
  // 管理后台（按角色显示）
  { to: "/admin/dashboard", label: "数据大盘", short: "大盘", icon: LayoutDashboard, roles: ["supervisor", "manager", "admin"] },
  { to: "/admin/staff", label: "客服账号", short: "账号", icon: Users, roles: ["admin"] },
  { to: "/admin/sla", label: "SLA", icon: Timer, roles: ["supervisor", "admin"] },
  { to: "/admin/audit", label: "操作审计", short: "操作", icon: ScrollText, roles: ["engineer", "admin"] },
  // Prompt 灰度后端鉴权仍是 require_admin(admin only)，故菜单 roles 保持 ["admin"]，
  // 与后端一致避免 engineer 点进去 403（统一到 engineer/admin 留 M2）。
  { to: "/admin/prompts", label: "Prompt 灰度", short: "灰度", icon: SlidersHorizontal, roles: ["admin"] },
  // M2 新增（路由由 Phase 1–6 各 task 注册）
  { to: "/admin/qa", label: "会话质检", short: "质检", icon: ClipboardCheck, roles: ["supervisor", "admin"] },
  { to: "/admin/performance", label: "客服绩效", short: "绩效", icon: UserCog, roles: ["supervisor", "admin"] },
  { to: "/admin/tools", label: "工具策略", short: "工具", icon: KeySquare, roles: ["engineer", "admin"] },
  { to: "/admin/cost", label: "成本大盘", short: "成本", icon: Wallet, roles: ["engineer", "manager", "admin"] },
  { to: "/admin/rbac", label: "角色权限", short: "RBAC", icon: Shield, roles: ["admin"] },
];

function useNavItems() {
  const { role } = useStaffSession();
  return NAV_ITEMS.filter((i) => !i.roles || (role != null && i.roles.includes(role)));
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
