import { App, Button, Card, Form, Input, Typography } from "antd";
import { useNavigate } from "react-router-dom";

import { staffLogin } from "../../api/staff";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title, Text } = Typography;

export function StaffLoginRoute() {
  const { login } = useStaffSession();
  const nav = useNavigate();
  const { message } = App.useApp();
  const [form] = Form.useForm<{ staff_id: string; password: string }>();

  async function onSubmit(values: { staff_id: string; password: string }) {
    try {
      const { token } = await staffLogin(
        values.staff_id.trim(),
        values.password,
      );
      login(token);
      nav("/staff/conversations");
    } catch {
      message.error("工号或密码错误");
    }
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center p-4"
      style={{ background: "#f5f5f5" }}
    >
      <Card style={{ width: "100%", maxWidth: 360 }}>
        <div className="flex flex-col items-center gap-2" style={{ marginBottom: 24 }}>
          <div
            style={{
              width: 40,
              height: 40,
              display: "grid",
              placeItems: "center",
              background: "#4f46e5",
              borderRadius: 6,
            }}
          >
            <span style={{ color: "#fff", fontSize: 18, fontWeight: 700 }}>
              T
            </span>
          </div>
          <Title level={4} style={{ margin: 0 }}>
            Tevau 客服 AI 引擎
          </Title>
          <Text type="secondary">客服工作台登录</Text>
        </div>
        <Form form={form} layout="vertical" onFinish={onSubmit}>
          <Form.Item
            name="staff_id"
            label="工号"
            rules={[{ required: true, message: "请输入工号" }]}
          >
            <Input placeholder="工号" autoComplete="username" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: "请输入密码" }]}
          >
            <Input.Password placeholder="密码" autoComplete="current-password" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" block>
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
