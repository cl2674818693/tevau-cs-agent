import type { MenuProps } from "antd";
import { Menu } from "antd";
import { useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useDynamicMenu } from "@/hooks/useDynamicMenu";
import { useSidebarCollapsed } from "@/hooks/useSidebarCollapsed";
import { useStaffSession } from "@/hooks/useStaffSession";

import {
  APP_BRAND_ICON,
  APP_BRAND_NAME,
  NAV_GROUPS,
  type NavItem,
} from "./nav-config";
import { PATH_TO_PERM } from "./perm-map";

type MenuItem = NonNullable<MenuProps["items"]>[number];

function canAccess(
  item: NavItem,
  role: string | null,
  matrix: ReturnType<typeof useDynamicMenu>["matrix"],
): boolean {
  const permKey = PATH_TO_PERM[item.to];
  if (matrix && permKey && role) return matrix.matrix[role]?.[permKey] === true;
  return !item.roles || (role != null && item.roles.includes(role));
}

/** 把 NAV_GROUPS 转换为 antd Menu 的 items API。
 *  顶层用 SubMenu（key=group.id, children=可见菜单项）以保留"分组可折叠"语义。 */
function buildMenuItems(
  role: string | null,
  matrix: ReturnType<typeof useDynamicMenu>["matrix"],
): MenuItem[] {
  return NAV_GROUPS.map((group) => {
    const visible = group.items.filter((i) => canAccess(i, role, matrix));
    if (visible.length === 0) return null;
    return {
      key: group.id,
      label: group.label,
      children: visible.map((i) => ({
        key: i.to,
        icon: <i.icon size={14} aria-hidden />,
        label: i.label,
      })),
    };
  }).filter(Boolean) as MenuItem[];
}

export function AppSidebar() {
  const { role } = useStaffSession();
  const { matrix } = useDynamicMenu();
  const { collapsed, toggle } = useSidebarCollapsed();
  const nav = useNavigate();
  const { pathname } = useLocation();
  const Brand = APP_BRAND_ICON;

  const items = useMemo(() => buildMenuItems(role, matrix), [role, matrix]);

  // 当前路径所属分组，决定 openKeys 默认值
  const openKeys = useMemo(
    () => NAV_GROUPS.filter((g) => !collapsed(g.id)).map((g) => g.id),
    [collapsed],
  );

  return (
    <div className="flex h-full flex-col bg-white">
      <div className="flex h-14 shrink-0 items-center gap-2 border-b border-gray-100 px-4">
        <Brand size={20} className="text-[--ant-color-primary]" aria-hidden />
        <span className="text-sm font-semibold">{APP_BRAND_NAME}</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        <Menu
          mode="inline"
          items={items}
          selectedKeys={[pathname]}
          openKeys={openKeys}
          onClick={({ key }) => nav(key)}
          onOpenChange={(keys) => {
            // 比较新旧 openKeys，把被切换的 groupId 写入 useSidebarCollapsed
            const before = new Set(openKeys);
            const after = new Set(keys);
            NAV_GROUPS.forEach((g) => {
              if (before.has(g.id) !== after.has(g.id)) toggle(g.id);
            });
          }}
          style={{ borderRight: 0 }}
        />
      </div>
    </div>
  );
}
