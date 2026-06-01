import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { setIdentity } from "../api/identity";

const { Title, Text } = Typography;

/** B 端主账户 ID 登录页（spec §4.1）。后端 /api/v1/auth/bu/login 在 task-04 落地。 */
export function BuLoginRoute() {
  const [err, setErr] = useState("");
  const nav = useNavigate();
  const [form] = Form.useForm<{ bu_id: string }>();

  async function onSubmit(values: { bu_id: string }) {
    setErr("");
    const r = await fetch("/api/v1/auth/bu/login", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bu_id: values.bu_id.trim() }),
    });
    if (!r.ok) {
      setErr((await r.text()) || "主账户不存在或已禁用");
      return;
    }
    setIdentity({ kind: "b", buId: values.bu_id.trim() });
    nav("/");
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
            Tevau AI 客服
          </Title>
          <Text type="secondary">合作伙伴技术支持</Text>
        </div>
        <Form form={form} layout="vertical" onFinish={onSubmit}>
          <Form.Item
            name="bu_id"
            label="主账户 ID"
            rules={[{ required: true, message: "请输入主账户 ID" }]}
          >
            <Input placeholder="主账户 ID / 租户 ID（例如 1011010000068）" />
          </Form.Item>
          {err && (
            <Alert
              type="error"
              showIcon
              title={err}
              style={{ marginBottom: 16 }}
            />
          )}
          <Form.Item style={{ marginBottom: 0 }}>
            <Button type="primary" htmlType="submit" block>
              进入对话
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
