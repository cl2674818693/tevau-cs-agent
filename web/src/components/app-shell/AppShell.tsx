import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { useStaffPresenceHeartbeat } from "@/hooks/useStaffPresenceHeartbeat";
import { useStaffSession } from "@/hooks/useStaffSession";
import { ThemeProvider } from "@/providers/ThemeProvider";
import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";
import { NAV_GROUPS, APP_BRAND_NAME } from "./nav-config";

/** 浏览器 title：{页面名} · {品牌}。 */
function useDocTitle(pathname: string) {
  for (const g of NAV_GROUPS) {
    const item = g.items.find((i) => pathname === i.to || pathname.startsWith(`${i.to}/`));
    if (item) {
      document.title = `${item.label} · ${APP_BRAND_NAME}`;
      return;
    }
  }
  document.title = APP_BRAND_NAME;
}

export function AppShell() {
  const { token } = useStaffSession();
  const { pathname } = useLocation();
  useStaffPresenceHeartbeat();
  useDocTitle(pathname);

  if (!token) return <Navigate to="/staff/login" replace />;

  return (
    <ThemeProvider>
      <div className="flex h-screen bg-background text-foreground">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppTopbar />
          <main className="flex-1 overflow-y-auto">
            <Outlet />
          </main>
        </div>
        <Toaster richColors closeButton />
      </div>
    </ThemeProvider>
  );
}
