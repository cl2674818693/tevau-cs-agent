import {
  Activity, BarChart3, BookOpen, CalendarClock,
  FileEdit, Headphones, Inbox, KeySquare,
  LayoutDashboard, Lightbulb, type LucideIcon, Route,
  Shield, ShieldAlert, ShieldCheck, SlidersHorizontal, Ticket,
  Timer, Users, Users2,
} from "lucide-react";

export type NavItem = {
  to: string;
  label: string;
  short?: string;
  icon: LucideIcon;
  roles?: string[];
};

export type NavGroup = {
  id: string;
  label: string;
  items: NavItem[];
};

export const NAV_GROUPS: NavGroup[] = [
  {
    id: "workbench",
    label: "工作台",
    items: [
      { to: "/staff/conversations", label: "会话", short: "会话", icon: Inbox },
      { to: "/staff/tickets", label: "工单", icon: Ticket },
      { to: "/staff/kpi", label: "KPI", icon: BarChart3 },
      { to: "/staff/insights", label: "知识缺口", short: "缺口", icon: Lightbulb },
      { to: "/staff/audits", label: "工具审计", short: "审计", icon: ShieldCheck },
    ],
  },
  {
    id: "ops",
    label: "运营看板",
    items: [
      { to: "/admin/dashboard", label: "数据大盘", icon: LayoutDashboard, roles: ["supervisor", "manager", "admin"] },
      { to: "/admin/sla", label: "SLA", icon: Timer, roles: ["supervisor", "admin"] },
    ],
  },
  {
    id: "ai",
    label: "AI 配置",
    items: [
      { to: "/admin/prompt-editor", label: "Prompt 编辑", icon: FileEdit, roles: ["engineer", "admin"] },
      { to: "/admin/prompts", label: "Prompt 灰度", icon: SlidersHorizontal, roles: ["admin"] },
      { to: "/admin/knowledge", label: "知识库", icon: BookOpen, roles: ["supervisor", "engineer", "admin"] },
      { to: "/admin/tools", label: "工具策略", icon: KeySquare, roles: ["engineer", "admin"] },
      { to: "/admin/guardrails", label: "范围拦截", icon: ShieldAlert, roles: ["engineer", "admin"] },
    ],
  },
  {
    id: "people",
    label: "坐席与权限",
    items: [
      { to: "/admin/staff", label: "客服账号", icon: Users, roles: ["admin"] },
      { to: "/admin/staff-groups", label: "客服分组", icon: Users2, roles: ["supervisor", "admin"] },
      { to: "/admin/presence", label: "在线状态", icon: Activity, roles: ["supervisor", "admin"] },
      { to: "/admin/shifts", label: "排班", icon: CalendarClock, roles: ["supervisor", "admin"] },
      { to: "/admin/routing", label: "会话路由", icon: Route, roles: ["supervisor", "admin"] },
      { to: "/admin/rbac", label: "角色权限", icon: Shield, roles: ["admin"] },
    ],
  },
];

export const APP_BRAND_ICON = Headphones;
export const APP_BRAND_NAME = "Tevau 客服 AI 引擎";
