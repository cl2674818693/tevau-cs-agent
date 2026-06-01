import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Breadcrumbs } from "./Breadcrumbs";
import { CommandPalette } from "./CommandPalette";
import { MobileSidebar } from "./MobileSidebar";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";

export function AppTopbar() {
  const [hint, setHint] = useState("⌘K");
  useEffect(() => {
    if (!navigator.userAgent.includes("Mac")) setHint("Ctrl+K");
  }, []);
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background px-3 md:px-4">
      <MobileSidebar />
      <div className="flex-1">
        <Breadcrumbs />
      </div>
      <Button
        variant="outline"
        size="sm"
        className="hidden gap-2 text-muted-foreground md:flex"
        onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))}
      >
        <Search className="h-3.5 w-3.5" />
        搜索菜单
        <kbd className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[10px]">{hint}</kbd>
      </Button>
      <ThemeToggle />
      <UserMenu />
      <CommandPalette />
    </header>
  );
}
