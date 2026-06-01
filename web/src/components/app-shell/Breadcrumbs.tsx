import { Breadcrumb } from "antd";
import { useLocation } from "react-router-dom";

import { NAV_GROUPS } from "./nav-config";

/** 用 pathname 在 NAV_GROUPS 中查询当前页所在分组与标题。 */
function resolveCrumb(pathname: string): { group: string; page: string } | null {
  for (const g of NAV_GROUPS) {
    const item = g.items.find(
      (i) => pathname === i.to || pathname.startsWith(`${i.to}/`),
    );
    if (item) return { group: g.label, page: item.label };
  }
  return null;
}

export function Breadcrumbs() {
  const { pathname } = useLocation();
  const crumb = resolveCrumb(pathname);
  if (!crumb) return null;
  return (
    <Breadcrumb
      items={[
        { title: crumb.group },
        { title: <span className="font-medium">{crumb.page}</span> },
      ]}
    />
  );
}
