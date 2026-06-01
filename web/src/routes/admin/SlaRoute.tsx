/**
 * SLA 策略与告警 —— antd v6 迁移参考模板。
 *
 * 后续 admin 路由请参考此文件的几个约定：
 *  1) 顶部用 `Flex` 排标题 + 右侧操作区，禁止再用旧的 PageContainer/PageHeader 组合。
 *  2) Card 包每个语义区块（KPI、表格、表单）。块间垂直间距用 Tailwind `space-y-*` 或 antd `Space`。
 *  3) Toast/通知统一从 `App.useApp().message` 取，禁止再 import sonner。
 *  4) 危险操作（停用/删除）用 `Popconfirm` 包，不再写 window.confirm。
 *  5) 加载态用 antd `Skeleton`，不要把 shadcn `<Skeleton/>` 留下。
 *  6) Tailwind 仅做布局（flex/gap/grid/spacing/text-color），所有"组件级"样式让 antd token 接管。
 */
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  SafetyCertificateOutlined,
} from "@ant-design/icons";
import {
  Alert,
  App,
  Button,
  Card,
  Flex,
  Form,
  InputNumber,
  Popconfirm,
  Select,
  Skeleton,
  Statistic,
  Table,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  createPolicy,
  deletePolicy,
  listBreaches,
  listPolicies,
  setPolicyActive,
  type SlaBreach,
  type SlaPolicy,
} from "../../api/adminSla";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title, Text } = Typography;

const METRIC_LABEL: Record<string, string> = {
  take_time: "接管时长",
  resolve_time: "解决时长",
};

// ─── Policy form ─────────────────────────────────────────────────────────────

function PolicyForm({ onCreated }: { onCreated: () => void }) {
  const { token } = useStaffSession();
  const { message } = App.useApp();
  const [form] = Form.useForm<{ metric: string; threshold_seconds: number }>();
  const [saving, setSaving] = useState(false);

  async function submit(values: { metric: string; threshold_seconds: number }) {
    if (!token) return;
    setSaving(true);
    try {
      await createPolicy(token, {
        metric: values.metric,
        threshold_seconds: values.threshold_seconds,
        scope: "all",
      });
      message.success("策略已新增");
      onCreated();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "创建失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Form
      form={form}
      layout="inline"
      initialValues={{ metric: "take_time", threshold_seconds: 300 }}
      onFinish={submit}
    >
      <Form.Item name="metric" label="指标" style={{ marginBottom: 0 }}>
        <Select
          style={{ width: 140 }}
          options={[
            { value: "take_time", label: "接管时长" },
            { value: "resolve_time", label: "解决时长" },
          ]}
        />
      </Form.Item>
      <Form.Item
        name="threshold_seconds"
        label="阈值（秒）"
        rules={[{ required: true, type: "number", min: 1 }]}
        style={{ marginBottom: 0 }}
      >
        <InputNumber min={1} style={{ width: 110 }} />
      </Form.Item>
      <Form.Item style={{ marginBottom: 0 }}>
        <Button type="primary" htmlType="submit" loading={saving}>
          新增策略
        </Button>
      </Form.Item>
    </Form>
  );
}

// ─── KPI derivation ──────────────────────────────────────────────────────────

function deriveKpi(policies: SlaPolicy[], breaches: SlaBreach[]) {
  const active = policies.filter((p) => p.active);
  const breachCount = breaches.length;
  // compliance rate: 无 active 策略时返回 null（UI 显示 "—"），避免 0/0 误读为 100%
  const breachedMetrics = new Set(breaches.map((b) => b.metric));
  const compliantCount = active.filter((p) => !breachedMetrics.has(p.metric)).length;
  const complianceRate =
    active.length > 0 ? (compliantCount / active.length) * 100 : null;

  const avgThreshold =
    active.length > 0
      ? Math.round(active.reduce((s, p) => s + p.threshold_seconds, 0) / active.length)
      : null;

  return { complianceRate, avgThreshold, breachCount };
}

// ─── Main route ───────────────────────────────────────────────────────────────

export function SlaRoute() {
  const { token, role } = useStaffSession();
  const { message } = App.useApp();
  const allowed = role === "supervisor" || role === "admin";

  const [policies, setPolicies] = useState<SlaPolicy[]>([]);
  const [breaches, setBreaches] = useState<SlaBreach[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    setErr("");
    Promise.all([listPolicies(token), listBreaches(token)])
      .then(([p, b]) => {
        setPolicies(p);
        setBreaches(b);
      })
      .catch(() => setErr("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setErr("需要主管或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  const kpi = useMemo(() => deriveKpi(policies, breaches), [policies, breaches]);

  // ── Policy table columns ──────────────────────────────────────────────────

  const policyCols: ColumnsType<SlaPolicy> = useMemo(
    () => [
      {
        title: "指标",
        dataIndex: "metric",
        render: (v: string) => METRIC_LABEL[v] ?? v,
      },
      {
        title: "阈值（秒）",
        dataIndex: "threshold_seconds",
        width: 120,
      },
      {
        title: "状态",
        dataIndex: "active",
        width: 100,
        render: (v: number) =>
          v ? <Tag color="success">启用</Tag> : <Tag>停用</Tag>,
      },
      {
        title: "操作",
        key: "actions",
        width: 160,
        render: (_: unknown, p: SlaPolicy) => (
          <Flex gap="middle">
            <Button
              type="link"
              size="small"
              style={{ padding: 0 }}
              onClick={async () => {
                if (!token) return;
                try {
                  await setPolicyActive(token, p.id, p.active ? 0 : 1);
                  reload();
                } catch (e) {
                  message.error(e instanceof Error ? e.message : "操作失败");
                }
              }}
            >
              {p.active ? "停用" : "启用"}
            </Button>
            <Popconfirm
              title="删除该策略？"
              description="删除后告警立即消失，可重新新增。"
              okText="确定删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={async () => {
                if (!token) return;
                try {
                  await deletePolicy(token, p.id);
                  reload();
                } catch (e) {
                  message.error(e instanceof Error ? e.message : "删除失败");
                }
              }}
            >
              <Button type="link" size="small" danger style={{ padding: 0 }}>
                删除
              </Button>
            </Popconfirm>
          </Flex>
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token],
  );

  // ── Breach table columns ──────────────────────────────────────────────────

  const breachCols: ColumnsType<SlaBreach> = useMemo(
    () => [
      {
        title: "会话",
        dataIndex: "conversation_id",
        render: (id: number) => (
          <Link to={`/staff/conversations/${id}`}>#{id}</Link>
        ),
      },
      {
        title: "指标",
        dataIndex: "metric",
        render: (v: string) => METRIC_LABEL[v] ?? v,
      },
      { title: "已用时（秒）", dataIndex: "elapsed_seconds", width: 130 },
      { title: "阈值（秒）", dataIndex: "threshold_seconds", width: 120 },
      {
        title: "超出（秒）",
        key: "overrun",
        width: 120,
        render: (_: unknown, b: SlaBreach) => (
          <Text type="danger" strong>
            +{b.elapsed_seconds - b.threshold_seconds}
          </Text>
        ),
      },
    ],
    [],
  );

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          SLA
        </Title>
        {allowed && !loading && <PolicyForm onCreated={reload} />}
      </Flex>

      {/* 操作说明：常驻展示，让首次进入此页的运营快速理解功能 */}
      <Alert
        type="info"
        showIcon
        icon={<InfoCircleOutlined />}
        title="SLA（服务水平协议）是什么"
        description={
          <div className="space-y-2">
            <p>
              为客服响应时长设定阈值。超时的会话会出现在下方
              <Text strong>"当前超时会话"</Text>列表里，
              并拉低<Text strong>"达标率"</Text>。判定是实时计算的——
              停用或删除策略后告警会立刻消失。
            </p>
            <ul className="ml-4 list-disc space-y-0.5">
              <li>
                <Text strong>接管时长（take_time）</Text>：
                会话进入"待人工接管"状态后，多少秒内必须有人 take。
              </li>
              <li>
                <Text strong>解决时长（resolve_time）</Text>：
                客服 take 后，多少秒内必须结案（resolved / release / transfer_out）。
              </li>
            </ul>
            <p>
              <Text strong>设置方式：</Text>
              右上角下拉选择指标 → 填阈值秒数 → 点"新增策略"。
              同一指标可建多条策略，<Text strong>按最严格阈值（最小值）判定</Text>。
            </p>
          </div>
        }
      />

      {err && <Alert type="error" showIcon title={err} />}

      {/* KPI 卡片 */}
      {loading ? (
        <div className="grid gap-3 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <Skeleton active paragraph={{ rows: 1 }} />
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-3">
          <Card>
            <Statistic
              title="达标率"
              value={kpi.complianceRate === null ? "—" : kpi.complianceRate}
              precision={kpi.complianceRate === null ? undefined : 1}
              suffix={kpi.complianceRate === null ? "" : "%"}
              valueStyle={{
                color:
                  kpi.complianceRate === null
                    ? undefined
                    : kpi.complianceRate >= 80
                      ? "#059669"
                      : "#dc2626",
              }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
          <Card>
            <Statistic
              title="平均响应阈值"
              value={kpi.avgThreshold === null ? "—" : kpi.avgThreshold}
              suffix={kpi.avgThreshold === null ? "" : "s"}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
          <Card>
            <Statistic
              title="未达标数"
              value={kpi.breachCount}
              valueStyle={{
                color: kpi.breachCount > 0 ? "#dc2626" : undefined,
              }}
              prefix={
                kpi.breachCount > 0 ? (
                  <ExclamationCircleOutlined />
                ) : (
                  <SafetyCertificateOutlined />
                )
              }
            />
          </Card>
        </div>
      )}

      {/* 当前超时告警 */}
      {!loading && breaches.length > 0 && (
        <Alert
          type="error"
          showIcon
          title={`当前 ${breaches.length} 个会话超时未处理`}
        />
      )}

      {/* 策略列表 */}
      <Card title="SLA 策略" size="small">
        <Table<SlaPolicy>
          rowKey="id"
          size="middle"
          columns={policyCols}
          dataSource={policies}
          loading={loading}
          pagination={false}
          locale={{ emptyText: "暂无策略，请在右上角新增" }}
        />
      </Card>

      {/* 超时会话列表 */}
      <Card title="当前超时会话" size="small">
        <Table<SlaBreach>
          rowKey={(r) => `${r.conversation_id}-${r.metric}`}
          size="middle"
          columns={breachCols}
          dataSource={breaches}
          loading={loading}
          pagination={false}
          locale={{ emptyText: "无超时会话" }}
        />
      </Card>
    </div>
  );
}
