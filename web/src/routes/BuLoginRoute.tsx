import { Alert, Button, Card, Form, Input, Typography } from "antd";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { setIdentity } from "../api/identity";

const { Title, Text } = Typography;

/** B 端主账户 ID 登录页（spec §4.1）。后端 /api/v1/auth/bu/login 在 task-04 落地。 */
export function BuLoginRoute() {
  const { t } = useTranslation();
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
      setErr((await r.text()) || t("buLogin.notFound"));
      return;
    }
    setIdentity({ kind: "b", buId: values.bu_id.trim() });
    nav("/");
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center p-4"
      style={{ background: "#f5f5f5", position: "relative" }}
    >
      <div style={{ position: "absolute", top: 16, right: 16 }}>
        <LanguageSwitcher size="small" />
      </div>
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
            {t("buLogin.title")}
          </Title>
          <Text type="secondary">{t("buLogin.subtitle")}</Text>
        </div>
        <Form form={form} layout="vertical" onFinish={onSubmit}>
          <Form.Item
            name="bu_id"
            label={t("buLogin.idLabel")}
            rules={[{ required: true, message: t("buLogin.idRequired") }]}
          >
            <Input placeholder={t("buLogin.idPlaceholder")} />
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
              {t("buLogin.submit")}
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
