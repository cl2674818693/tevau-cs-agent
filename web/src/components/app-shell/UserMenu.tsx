import { LogoutOutlined, UserOutlined } from "@ant-design/icons";
import { Avatar, Dropdown, type MenuProps } from "antd";
import { useNavigate } from "react-router-dom";

import { useStaffSession } from "@/hooks/useStaffSession";

export function UserMenu() {
  const { role, logout } = useStaffSession();
  const nav = useNavigate();
  const initial = role ? role[0].toUpperCase() : "?";

  const items: MenuProps["items"] = [
    {
      key: "role",
      icon: <UserOutlined />,
      label: <span className="text-xs text-gray-500">角色：{role ?? "(未登录)"}</span>,
      disabled: true,
    },
    { type: "divider" },
    {
      key: "logout",
      icon: <LogoutOutlined />,
      label: "退出",
      onClick: () => {
        logout();
        nav("/staff/login");
      },
    },
  ];

  return (
    <Dropdown menu={{ items }} placement="bottomRight" trigger={["click"]}>
      <Avatar
        size="small"
        style={{ backgroundColor: "#4f46e5", cursor: "pointer" }}
        aria-label="账号菜单"
      >
        {initial}
      </Avatar>
    </Dropdown>
  );
}
