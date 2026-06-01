import { Layout } from "antd";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useStaffPresenceHeartbeat } from "@/hooks/useStaffPresenceHeartbeat";
import { useStaffSession } from "@/hooks/useStaffSession";

import { AppSidebar } from "./AppSidebar";
import { AppTopbar } from "./AppTopbar";
import { APP_BRAND_NAME, NAV_GROUPS } from "./nav-config";

/** 浏览器 title：{页面名} · {品牌}。 */
function useDocTitle(pathname: string) {
  for (const g of NAV_GROUPS) {
    const item = g.items.find(
      (i) => pathname === i.to || pathname.startsWith(`${i.to}/`),
    );
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
    <Layout style={{ minHeight: "100vh" }}>
      <Layout.Sider
        width={240}
        theme="light"
        breakpoint="md"
        collapsedWidth={0}
        style={{ borderRight: "1px solid #f0f0f0" }}
      >
        <AppSidebar />
      </Layout.Sider>
      <Layout>
        <Layout.Header
          style={{
            background: "#fff",
            padding: "0 16px",
            borderBottom: "1px solid #f0f0f0",
            height: 56,
            lineHeight: "56px",
          }}
        >
          <AppTopbar />
        </Layout.Header>
        <Layout.Content style={{ overflow: "auto" }}>
          <Outlet />
        </Layout.Content>
      </Layout>
    </Layout>
  );
}
