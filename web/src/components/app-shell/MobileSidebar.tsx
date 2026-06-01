import { Menu } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { AppSidebar } from "./AppSidebar";

/** < md 时显示。点汉堡按钮打开 Sheet，Sheet 内复用 AppSidebar（强制显示）。 */
export function MobileSidebar() {
  const [open, setOpen] = useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden" aria-label="打开菜单">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-72 p-0">
        <div className="!flex h-full" onClick={() => setOpen(false)}>
          {/* AppSidebar 自带 hidden md:flex，这里包一层强制显示 */}
          <div className="flex h-full w-full [&_aside]:!flex">
            <AppSidebar />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
