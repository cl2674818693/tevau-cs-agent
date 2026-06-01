import { LockOutlined } from "@ant-design/icons";
import { Button, Result } from "antd";
import { useNavigate } from "react-router-dom";

export function ForbiddenRoute() {
  const nav = useNavigate();
  return (
    <Result
      icon={<LockOutlined style={{ color: "rgba(0,0,0,0.45)" }} />}
      title="403 · 无权限"
      subTitle="您当前角色无法访问此页面"
      extra={
        <Button onClick={() => nav("/staff/conversations")}>返回工作台</Button>
      }
    />
  );
}
