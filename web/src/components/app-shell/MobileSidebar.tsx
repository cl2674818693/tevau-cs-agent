import { MenuOutlined } from "@ant-design/icons";
import { Button, Drawer } from "antd";
import { useState } from "react";

import { AppSidebar } from "./AppSidebar";

/** < md 时显示。点汉堡按钮打开 Drawer，Drawer 内复用 AppSidebar。 */
export function MobileSidebar() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        type="text"
        icon={<MenuOutlined />}
        className="md:!hidden"
        onClick={() => setOpen(true)}
        aria-label="打开菜单"
      />
      <Drawer
        open={open}
        placement="left"
        size="default"
        onClose={() => setOpen(false)}
        styles={{ body: { padding: 0 } }}
        closable={false}
      >
        <div className="h-full">
          <AppSidebar onNavigate={() => setOpen(false)} />
        </div>
      </Drawer>
    </>
  );
}
