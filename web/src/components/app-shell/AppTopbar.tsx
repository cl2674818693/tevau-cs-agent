import { SearchOutlined } from "@ant-design/icons";
import { Button, Flex } from "antd";
import { useEffect, useState } from "react";

import { Breadcrumbs } from "./Breadcrumbs";
import { CommandPalette } from "./CommandPalette";
import { MobileSidebar } from "./MobileSidebar";
import { UserMenu } from "./UserMenu";

export function AppTopbar() {
  const [hint, setHint] = useState("⌘K");
  useEffect(() => {
    if (!navigator.userAgent.includes("Mac")) setHint("Ctrl+K");
  }, []);
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
      <Button
        size="small"
        icon={<SearchOutlined />}
        className="!hidden md:!inline-flex"
        onClick={() =>
          window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }))
        }
      >
        搜索菜单
        <kbd
          style={{
            marginLeft: 8,
            padding: "1px 6px",
            fontSize: 10,
            background: "rgba(0, 0, 0, 0.04)",
            borderRadius: 4,
          }}
        >
          {hint}
        </kbd>
      </Button>
      <UserMenu />
      <CommandPalette />
    </Flex>
  );
}
