import { CopyOutlined } from "@ant-design/icons";
import { App, Button, Card, Flex, Tag, Tooltip, Typography } from "antd";

import type { StaffConversation } from "../api/staff";

const { Text } = Typography;

type Props = {
  conv: StaffConversation | null;
  loading?: boolean;
};

const MODE_COLOR: Record<string, string> = {
  ai: "default",
  ai_draft: "purple",
  human_pending: "orange",
  human_takeover: "blue",
};

const MODE_LABEL: Record<string, string> = {
  ai: "AI 对话",
  ai_draft: "AI 草稿模式",
  human_pending: "等待人工",
  human_takeover: "人工接管",
};

const RISK_BADGES: {
  key: keyof StaffConversation;
  label: string;
  color: string;
}[] = [
  { key: "has_failed", label: "失败", color: "red" },
  { key: "has_downvote", label: "差评", color: "red" },
  { key: "has_out_of_scope", label: "范围外", color: "orange" },
  { key: "has_empty_tool", label: "空结果", color: "default" },
  { key: "needs_review", label: "待复核", color: "blue" },
];

/** 会话详情页右侧栏：会话元信息 + 风险标记。配合后端 get_meta_with_risk 返回口径。 */
export function ConversationInfoCard({ conv, loading }: Props) {
  if (!conv) {
    return (
      <Card size="small" title="会话信息" loading={loading}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          —
        </Text>
      </Card>
    );
  }

  const risks = RISK_BADGES.filter((b) => !!conv[b.key]);
  const elapsed = formatElapsed(conv);

  return (
    <Card size="small" title="会话信息">
      <Flex vertical gap={10}>
        <Row label="会话 ID" value={`#${conv.id}`} mono />
        <Row
          label="用户类型"
          value={conv.user_type === "c" ? "C 端用户" : "BU"}
        />
        <Row label="Subject" value={conv.subject_id} mono copyable />
        <Row
          label="模式"
          custom={
            <Tag color={MODE_COLOR[conv.mode] ?? "default"}>
              {MODE_LABEL[conv.mode] ?? conv.mode}
            </Tag>
          }
        />
        <Row label="负责客服" value={conv.assigned_staff_id ?? "—"} mono />
        <Row label="创建时间" value={formatUtcLocal(conv.created_at)} mono />
        {elapsed && <Row label={elapsed.label} value={elapsed.value} />}
        <div>
          <Text type="secondary" style={{ fontSize: 11 }}>
            风险标记
          </Text>
          <div style={{ marginTop: 4 }}>
            {risks.length === 0 ? (
              <Text type="secondary" style={{ fontSize: 12 }}>
                —
              </Text>
            ) : (
              <Flex wrap="wrap" gap={4}>
                {risks.map((b) => (
                  <Tag key={b.key} color={b.color}>
                    {b.label}
                  </Tag>
                ))}
              </Flex>
            )}
          </div>
        </div>
      </Flex>
    </Card>
  );
}

function Row({
  label,
  value,
  custom,
  mono,
  copyable,
}: {
  label: string;
  value?: string;
  custom?: React.ReactNode;
  mono?: boolean;
  copyable?: boolean;
}) {
  // 项目规范：App.useApp().message 而非 antd 顶层 message（locale/theme/holder 走 ConfigProvider context）。
  const { message } = App.useApp();
  return (
    <div>
      <Text type="secondary" style={{ fontSize: 11 }}>
        {label}
      </Text>
      <Flex align="center" gap={4} style={{ marginTop: 2 }}>
        {custom ?? (
          <span
            style={{
              fontSize: 12,
              fontFamily: mono ? "ui-monospace, monospace" : undefined,
              wordBreak: "break-all",
            }}
          >
            {value}
          </span>
        )}
        {copyable && value && (
          <Tooltip title="复制">
            <Button
              type="text"
              size="small"
              icon={<CopyOutlined />}
              onClick={() => {
                // navigator.clipboard 在非 HTTPS / 旧浏览器 / file:// 不可用，
                // 必须显式检查再弹成功，避免 optional chaining 静默失败误导。
                if (!navigator.clipboard?.writeText) {
                  message.warning("当前环境无法访问剪贴板，请手动复制");
                  return;
                }
                navigator.clipboard
                  .writeText(value)
                  .then(() => message.success("已复制"))
                  .catch(() => message.error("复制失败"));
              }}
            />
          </Tooltip>
        )}
      </Flex>
    </div>
  );
}

/** 等待 / 接管时长：human_pending 显示已等待，human_takeover 显示接管多久。 */
function formatElapsed(
  conv: StaffConversation,
): { label: string; value: string } | null {
  if (conv.mode === "human_pending") {
    return { label: "已等待", value: humanize(sinceSeconds(conv.created_at)) };
  }
  if (conv.mode === "human_takeover") {
    const ref = conv.assigned_at ?? conv.created_at;
    return { label: "接管时长", value: humanize(sinceSeconds(ref)) };
  }
  return null;
}

function sinceSeconds(isoLike: string): number {
  // 后端 created_at 格式 "YYYY-MM-DD HH:MM:SS"（UTC）。fromISO 需要 'T' 分隔。
  const t = Date.parse(isoLike.replace(" ", "T") + "Z");
  if (Number.isNaN(t)) return 0;
  return Math.max(0, Math.floor((Date.now() - t) / 1000));
}

/** 后端 UTC 字符串 "YYYY-MM-DD HH:MM:SS" → 本地时区可读时间，避免客服按本地时间误读。
 *  补 'Z' 显式标 UTC；某些浏览器解析无 Z 的字符串会当本地时间，差 8h（中国） */
function formatUtcLocal(raw: string): string {
  if (!raw) return "—";
  const t = Date.parse(raw.replace(" ", "T") + "Z");
  if (Number.isNaN(t)) return raw;
  return new Date(t).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function humanize(sec: number): string {
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
  return `${Math.floor(sec / 86400)}d`;
}
