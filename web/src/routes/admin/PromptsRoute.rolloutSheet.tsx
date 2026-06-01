import { App, Button, Drawer, Form, InputNumber } from "antd";
import { useEffect } from "react";

import { setRollout } from "../../api/admin";

import type { PromptRow } from "./PromptsRoute.columns";

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  row: PromptRow | null;
  token: string;
  currentRollout: Record<string, number>;
  onSuccess: (next: Record<string, number>) => void;
};

export function RolloutSheet({
  open,
  onOpenChange,
  row,
  token,
  currentRollout,
  onSuccess,
}: Props) {
  const [form] = Form.useForm<{ pct: number }>();
  const { message } = App.useApp();

  useEffect(() => {
    if (open && row) form.setFieldsValue({ pct: row.rollout });
  }, [open, row, form]);

  async function onSubmit(values: { pct: number }) {
    if (!row) return;
    const next = { ...currentRollout, [row.version]: values.pct };
    const total = Object.values(next).reduce((a, b) => a + (b || 0), 0);
    if (total > 100) {
      form.setFields([{ name: "pct", errors: [`合计将达 ${total}%，超过 100`] }]);
      return;
    }
    try {
      const saved = await setRollout(token, next);
      message.success("已保存并热加载");
      onSuccess(saved);
      onOpenChange(false);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "保存失败");
    }
  }

  const total = Object.values(currentRollout).reduce((a, b) => a + (b || 0), 0);

  return (
    <Drawer
      title={`调整流量 — ${row?.version ?? ""}`}
      open={open}
      onClose={() => onOpenChange(false)}
      size="default"
    >
      <div
        style={{
          background: "rgba(0,0,0,0.03)",
          borderRadius: 6,
          padding: "12px 16px",
          marginBottom: 20,
          fontSize: 13,
          color: "rgba(0,0,0,0.65)",
        }}
      >
        <p style={{ margin: 0 }}>
          当前所有版本合计：<strong>{total}%</strong>
        </p>
        <p style={{ margin: "4px 0 0 0", fontSize: 12 }}>
          余量自动回落到 default 版本
        </p>
      </div>
      <Form form={form} layout="vertical" onFinish={onSubmit}>
        <Form.Item
          name="pct"
          label={
            <>
              流量比例（%）—{" "}
              <span style={{ fontFamily: "ui-monospace, monospace" }}>
                {row?.version}
              </span>
            </>
          }
          rules={[
            { required: true, type: "number", min: 0, max: 100 },
          ]}
        >
          <InputNumber min={0} max={100} style={{ width: "100%" }} />
        </Form.Item>
        <Form.Item style={{ marginBottom: 0 }}>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <Button onClick={() => onOpenChange(false)}>取消</Button>
            <Button type="primary" htmlType="submit">
              保存
            </Button>
          </div>
        </Form.Item>
      </Form>
    </Drawer>
  );
}
