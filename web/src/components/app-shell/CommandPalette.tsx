import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CommandDialog, CommandEmpty, CommandGroup, CommandInput,
  CommandItem, CommandList,
} from "@/components/ui/command";
import { useDynamicMenu } from "@/hooks/useDynamicMenu";
import { useStaffSession } from "@/hooks/useStaffSession";
import { NAV_GROUPS, type NavItem } from "./nav-config";
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

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const { role } = useStaffSession();
  const { matrix } = useDynamicMenu();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="搜索菜单…" />
      <CommandList>
        <CommandEmpty>未找到匹配项</CommandEmpty>
        {NAV_GROUPS.map((group) => {
          const visible = group.items.filter((i) => canAccess(i, role, matrix));
          if (visible.length === 0) return null;
          return (
            <CommandGroup key={group.id} heading={group.label}>
              {visible.map((item) => (
                <CommandItem
                  key={item.to}
                  value={`${group.label} ${item.label}`}
                  onSelect={() => {
                    setOpen(false);
                    nav(item.to);
                  }}
                >
                  <item.icon className="mr-2 h-4 w-4" />
                  {item.label}
                </CommandItem>
              ))}
            </CommandGroup>
          );
        })}
      </CommandList>
    </CommandDialog>
  );
}
