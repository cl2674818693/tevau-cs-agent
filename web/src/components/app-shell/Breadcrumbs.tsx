import { useLocation } from "react-router-dom";
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList,
  BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { NAV_GROUPS } from "./nav-config";

/** 用 pathname 在 NAV_GROUPS 中查询当前页所在分组与标题。 */
function resolveCrumb(pathname: string): { group: string; page: string } | null {
  for (const g of NAV_GROUPS) {
    const item = g.items.find((i) => pathname === i.to || pathname.startsWith(`${i.to}/`));
    if (item) return { group: g.label, page: item.label };
  }
  return null;
}

export function Breadcrumbs() {
  const { pathname } = useLocation();
  const crumb = resolveCrumb(pathname);
  if (!crumb) return null;
  return (
    <Breadcrumb>
      <BreadcrumbList>
        <BreadcrumbItem className="hidden md:block">
          <BreadcrumbLink className="text-muted-foreground">{crumb.group}</BreadcrumbLink>
        </BreadcrumbItem>
        <BreadcrumbSeparator className="hidden md:block" />
        <BreadcrumbItem>
          <BreadcrumbPage>{crumb.page}</BreadcrumbPage>
        </BreadcrumbItem>
      </BreadcrumbList>
    </Breadcrumb>
  );
}
