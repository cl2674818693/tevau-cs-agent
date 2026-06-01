import { ChevronDown } from "lucide-react";
import { NavLink } from "react-router-dom";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useDynamicMenu } from "@/hooks/useDynamicMenu";
import { useSidebarCollapsed } from "@/hooks/useSidebarCollapsed";
import { useStaffSession } from "@/hooks/useStaffSession";
import { cn } from "@/lib/utils";
import { APP_BRAND_ICON, APP_BRAND_NAME, NAV_GROUPS, type NavItem } from "./nav-config";
import { PATH_TO_PERM } from "./perm-map";

function canAccess(
  item: NavItem,
  role: string | null,
  matrix: ReturnType<typeof useDynamicMenu>["matrix"],
): boolean {
  const permKey = PATH_TO_PERM[item.to];
  if (matrix && permKey && role) return matrix.matrix[role]?.[permKey] === true;
  return !item.roles || (role != null && item.roles.includes(role));
}

export function AppSidebar() {
  const { role } = useStaffSession();
  const { matrix } = useDynamicMenu();
  const { collapsed, toggle } = useSidebarCollapsed();
  const Brand = APP_BRAND_ICON;

  return (
    <aside className="hidden h-full w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex">
      <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
        <Brand className="h-5 w-5 text-primary" aria-hidden />
        <span className="text-sm font-semibold">{APP_BRAND_NAME}</span>
      </div>
      <ScrollArea className="flex-1 px-2 py-2">
        {NAV_GROUPS.map((group) => {
          const visible = group.items.filter((i) => canAccess(i, role, matrix));
          if (visible.length === 0) return null;
          const isOpen = !collapsed(group.id);
          return (
            <Collapsible key={group.id} open={isOpen} onOpenChange={() => toggle(group.id)} className="mb-1">
              <CollapsibleTrigger className="flex w-full items-center justify-between rounded px-3 py-1.5 text-xs font-semibold text-sidebar-foreground/60 hover:bg-sidebar-accent">
                <span>{group.label}</span>
                <ChevronDown className={cn("h-3 w-3 transition-transform", !isOpen && "-rotate-90")} aria-hidden />
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-0.5 space-y-0.5">
                {visible.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors",
                        isActive
                          ? "bg-sidebar-primary text-sidebar-primary-foreground"
                          : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                      )
                    }
                  >
                    <item.icon className="h-4 w-4 shrink-0" aria-hidden />
                    {item.label}
                  </NavLink>
                ))}
              </CollapsibleContent>
            </Collapsible>
          );
        })}
      </ScrollArea>
    </aside>
  );
}
