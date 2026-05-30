import { Link } from "react-router-dom";

import { Alert } from "../../components/ui/alert";
import { Card } from "../../components/ui/card";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { useStaffSession } from "../../hooks/useStaffSession";

const ROLES = ["agent", "senior", "supervisor", "engineer", "manager", "admin"];

type ModuleRow = {
  path: string;
  label: string;
  roles: string[];
};

const MODULES: ModuleRow[] = [
  { path: "/admin/dashboard",   label: "数据大盘",      roles: ["supervisor", "manager", "admin"] },
  { path: "/admin/staff",       label: "客服账号",      roles: ["admin"] },
  { path: "/admin/performance", label: "客服绩效",      roles: ["supervisor", "admin"] },
  { path: "/admin/qa",          label: "会话质检",      roles: ["supervisor", "admin"] },
  { path: "/admin/sla",         label: "SLA 配置",      roles: ["supervisor", "admin"] },
  { path: "/admin/tools",       label: "工具策略",      roles: ["engineer", "admin"] },
  { path: "/admin/cost",        label: "成本大盘",      roles: ["engineer", "manager", "admin"] },
  { path: "/admin/audit",       label: "操作审计",      roles: ["engineer", "admin"] },
  { path: "/admin/prompts",     label: "Prompt 灰度",   roles: ["admin"] },
  { path: "/admin/rbac",        label: "角色权限",      roles: ["admin"] },
];

function RoleMatrix() {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-body3">
          <thead>
            <tr className="border-b border-line text-ink-secondary">
              <th className="px-3 py-2 text-left font-normal">模块</th>
              {ROLES.map((r) => (
                <th key={r} className="px-3 py-2 text-center font-normal">{r}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MODULES.map((m) => (
              <tr key={m.path} className="border-b border-line last:border-0">
                <td className="px-3 py-2 text-ink-primary">
                  <Link to={m.path} className="text-brand">{m.label}</Link>
                </td>
                {ROLES.map((r) => (
                  <td key={r} className="px-3 py-2 text-center">
                    {m.roles.includes(r) ? (
                      <span className="text-status-success">✓</span>
                    ) : (
                      <span className="text-ink-tertiary">·</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function RbacRoute() {
  const { role } = useStaffSession();
  if (role !== "admin") {
    return (
      <PageContainer width="wide">
        <PageHeader title="角色权限" />
        <Alert variant="error">需要管理员权限</Alert>
      </PageContainer>
    );
  }
  return (
    <PageContainer width="wide">
      <PageHeader title="角色权限（只读）" />
      <p className="mb-3 text-body3 text-ink-secondary">
        M2 阶段一：展示六角色在各模块的可见性。改角色请到
        <Link to="/admin/staff" className="ml-1 text-brand">客服账号</Link>
        页面操作。M3 将引入 role_permissions 表支持自定义。
      </p>
      <RoleMatrix />
    </PageContainer>
  );
}
