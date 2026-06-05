import { SearchOutlined } from "@ant-design/icons";
import { Flex } from "antd";
import { useEffect, useState } from "react";

import { PresenceToggle } from "@/components/PresenceToggle";
import { useStaffSession } from "@/hooks/useStaffSession";
import { Breadcrumbs } from "./Breadcrumbs";
import { CommandPalette } from "./CommandPalette";
import { MobileSidebar } from "./MobileSidebar";
import { UserMenu } from "./UserMenu";

export function AppTopbar() {
  const [hint, setHint] = useState("⌘K");
  useEffect(() => {
    if (!navigator.userAgent.includes("Mac")) setHint("Ctrl+K");
  }, []);
  const { token, role } = useStaffSession();
  const canDispatch = !!token && ["agent", "senior", "supervisor", "admin"].includes(role ?? "");
  return (
    <Flex
      align="center"
      gap="small"
      style={{ height: "100%", width: "100%" }}
    >
      <MobileSidebar />
      <div style={{ flex: 1 }}>
        <Breadcrumbs />
      </div>
      <button
        type="button"
        className="hidden md:inline-flex"
        onClick={() =>
          window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))
        }
        style={{
          alignItems: "center",
          gap: 8,
          height: 28,
          padding: "0 10px",
          border: "1px solid #d9d9d9",
          borderRadius: 6,
          background: "#fff",
          color: "rgba(0, 0, 0, 0.45)",
          fontSize: 13,
          lineHeight: 1,
          cursor: "pointer",
        }}
      >
        <SearchOutlined />
        <span>搜索菜单</span>
        <kbd
          style={{
            padding: "1px 6px",
            fontSize: 10,
            background: "rgba(0, 0, 0, 0.04)",
            borderRadius: 4,
            fontFamily: "inherit",
          }}
        >
          {hint}
        </kbd>
      </button>
      {canDispatch && token && <PresenceToggle token={token} />}
      <UserMenu />
      <CommandPalette />
    </Flex>
  );
}
