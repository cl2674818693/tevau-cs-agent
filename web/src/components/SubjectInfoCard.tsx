import { Card, Descriptions, Flex, Skeleton, Tag, Tooltip, Typography } from "antd";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useEffect, useState } from "react";

import { getSubjectInfo, type SubjectInfo } from "../api/staff";

const { Text } = Typography;

type Props = {
  token: string | null;
  convId: number;
};

/**
 * H5 下窗口 < 768px 时默认折叠，标题行显示一行摘要 chip；桌面端默认展开 + 无 toggle 按钮。
 * 用 matchMedia 探测断点（不用 Tailwind 的 md:hidden 响应式 class，那个 className 里的 `:`
 * 在 jsdom + nwsapi 下会被某个查询误解析为 `:hidden` 伪类，导致 getByRole 抛 SyntaxError）。
 */
function useIsMobile(breakpoint = 768): boolean {
  const [isMobile, setIsMobile] = useState(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return !window.matchMedia(`(min-width: ${breakpoint}px)`).matches;
  });
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia(`(min-width: ${breakpoint}px)`);
    const handler = (e: MediaQueryListEvent) => setIsMobile(!e.matches);
    mq.addEventListener?.("change", handler);
    return () => mq.removeEventListener?.("change", handler);
  }, [breakpoint]);
  return isMobile;
}

export function SubjectInfoCard({ token, convId }: Props) {
  const [data, setData] = useState<SubjectInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const isMobile = useIsMobile();
  // 移动端默认折叠；桌面端默认展开。窗口跨越断点也跟随重置（mq change 触发 isMobile 更新，
  // 这里独立维护 collapsed 让用户的手动展开/折叠不被尺寸抖动覆盖）。
  const [collapsed, setCollapsed] = useState(true);
  useEffect(() => {
    setCollapsed(isMobile);
  }, [isMobile]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    setErr("");
    getSubjectInfo(token, convId)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch(() => {
        if (!cancelled) setErr("拉取用户信息失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, convId]);

  if (loading) {
    return (
      <Card size="small" title="用户信息" loading>
        <Skeleton active paragraph={{ rows: 3 }} />
      </Card>
    );
  }
  if (err || !data) {
    return (
      <Card size="small" title="用户信息">
        <Text type="secondary" style={{ fontSize: 12 }}>
          {err || "—"}
        </Text>
      </Card>
    );
  }

  const { subject, client_info } = data;
  const isC = subject.user_type === "c";
  const summary = summarize(data);
  // 桌面端永远展开 + 无 toggle；移动端按 collapsed 决定。
  const bodyHidden = isMobile && collapsed;
  const showToggle = isMobile;
  const showSummary = isMobile && collapsed && !!summary;

  return (
    <Card
      size="small"
      title={
        <Flex align="center" gap="small" wrap="nowrap" style={{ minWidth: 0 }}>
          <span style={{ flexShrink: 0 }}>用户信息</span>
          {showSummary && (
            <Text
              type="secondary"
              ellipsis
              style={{
                fontSize: 12,
                fontWeight: 400,
                minWidth: 0,
                flex: 1,
              }}
            >
              {summary}
            </Text>
          )}
        </Flex>
      }
      extra={
        showToggle ? (
          <button
            type="button"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? "展开用户信息" : "折叠用户信息"}
            style={{
              background: "none",
              border: 0,
              cursor: "pointer",
              padding: 4,
              color: "rgba(0,0,0,0.55)",
              display: "inline-flex",
              alignItems: "center",
            }}
          >
            {collapsed ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronUp className="h-4 w-4" />
            )}
          </button>
        ) : null
      }
    >
      <div style={{ display: bodyHidden ? "none" : "block" }}>
        <Flex vertical gap={12}>
          {subject.found ? (
            isC ? (
              <CSubjectBlock s={subject} />
            ) : (
              <BSubjectBlock s={subject} />
            )
          ) : (
            <Text type="secondary" style={{ fontSize: 12 }}>
              业务库未关联或主体不存在
            </Text>
          )}

          {/* 客户端环境（H5 上报）：业务无关，单独分块，没数据时不显示分块 */}
          {client_info && (
            <>
              <Divider />
              <ClientBlock c={client_info} />
            </>
          )}
        </Flex>
      </div>
    </Card>
  );
}

/** 折叠态摘要 chip：取主体名 + 状态 + 平台，三件套 `·` 分隔，不存在的字段跳过。 */
function summarize(d: SubjectInfo | null): string {
  if (!d) return "";
  const { subject, client_info } = d;
  if (!subject.found) {
    return ["未关联业务库", client_info?.platform].filter(Boolean).join(" · ");
  }
  const isC = subject.user_type === "c";
  const name = isC
    ? subject.nick_name || subject.user_code || subject.subject_id
    : subject.company_name || subject.subject_id;
  const status = isC
    ? subject.user_status || subject.kyc_status
    : subject.status;
  return [name, status, client_info?.platform].filter(Boolean).join(" · ");
}

function Divider() {
  return <div style={{ borderTop: "1px dashed #f0f0f0", margin: "4px 0" }} />;
}

function CSubjectBlock({ s }: { s: SubjectInfo["subject"] }) {
  return (
    <>
      <Descriptions
        size="small"
        column={1}
        styles={{
          label: { fontSize: 11, color: "rgba(0,0,0,0.45)", width: 76 },
          content: { fontSize: 12 },
        }}
        items={[
          { key: "nick", label: "昵称", children: s.nick_name ?? "—" },
          { key: "uc", label: "User Code", children: s.user_code ?? "—" },
          { key: "phone", label: "手机", children: s.phone ?? "—" },
          { key: "email", label: "邮箱", children: s.email ?? "—" },
          {
            key: "us",
            label: "账户状态",
            children: <Tag color={statusColor(s.user_status)}>{s.user_status ?? "—"}</Tag>,
          },
          {
            key: "kyc",
            label: "KYC",
            children: <Tag color={kycColor(s.kyc_status)}>{s.kyc_status ?? "—"}</Tag>,
          },
          { key: "card", label: "开卡", children: s.open_card_status ?? "—" },
          { key: "reg", label: "注册", children: shortDate(s.registration_time) },
          { key: "last", label: "上次登录", children: shortDate(s.last_login_time) },
        ]}
      />
      {s.recent_30d_transactions && s.recent_30d_transactions.length > 0 && (
        <div>
          <Text type="secondary" style={{ fontSize: 11 }}>
            近 30 天交易
          </Text>
          <Flex wrap="wrap" gap={4} style={{ marginTop: 4 }}>
            {s.recent_30d_transactions.map((t) => (
              <Tag key={t.currency}>
                {t.currency} {t.count}笔 / {t.amount}
              </Tag>
            ))}
          </Flex>
        </div>
      )}
      {(!s.recent_30d_transactions || s.recent_30d_transactions.length === 0) && (
        <Text type="secondary" style={{ fontSize: 11 }}>
          近 30 天无成功交易
        </Text>
      )}
    </>
  );
}

function BSubjectBlock({ s }: { s: SubjectInfo["subject"] }) {
  return (
    <Descriptions
      size="small"
      column={1}
      styles={{
        label: { fontSize: 11, color: "rgba(0,0,0,0.45)", width: 76 },
        content: { fontSize: 12 },
      }}
      items={[
        { key: "name", label: "公司名", children: s.company_name ?? "—" },
        { key: "tid", label: "Tenant", children: s.tenant_id ?? s.subject_id },
        {
          key: "st",
          label: "状态",
          children: <Tag color={buStatusColor(s.status)}>{s.status ?? "—"}</Tag>,
        },
      ]}
    />
  );
}

function ClientBlock({ c }: { c: NonNullable<SubjectInfo["client_info"]> }) {
  return (
    <Descriptions
      size="small"
      column={1}
      styles={{
        label: { fontSize: 11, color: "rgba(0,0,0,0.45)", width: 76 },
        content: { fontSize: 12 },
      }}
      items={[
        { key: "p", label: "平台", children: c.platform ?? "—" },
        { key: "v", label: "APP 版本", children: c.app_version ?? "—" },
        {
          key: "ua",
          label: "UA",
          children: c.user_agent ? (
            <Tooltip title={c.user_agent}>
              <span style={{ fontSize: 11, color: "rgba(0,0,0,0.55)" }}>
                {c.user_agent.length > 40 ? c.user_agent.slice(0, 40) + "…" : c.user_agent}
              </span>
            </Tooltip>
          ) : (
            "—"
          ),
        },
      ]}
    />
  );
}

function statusColor(s: string | undefined): string {
  if (s === "正常") return "green";
  if (s === "冻结") return "orange";
  if (s === "注销") return "red";
  return "default";
}

function kycColor(s: string | undefined): string {
  if (s === "已认证") return "green";
  if (s === "审核中") return "blue";
  if (s === "认证失败") return "red";
  return "default";
}

function buStatusColor(s: string | undefined): string {
  if (s === "运行中") return "green";
  if (s === "已停用") return "red";
  if (s === "待开启") return "default";
  return "default";
}

/** "YYYY-MM-DD HH:MM:SS" UTC → "YYYY-MM-DD"。后端给的是 datetime 字符串，列表场景只看日期。 */
function shortDate(s: string | undefined): string {
  if (!s) return "—";
  // 业务库返回的可能是 datetime 串，截前 10 位即可
  return s.slice(0, 10);
}
