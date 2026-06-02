import { Card, Descriptions, Flex, Skeleton, Tag, Tooltip, Typography } from "antd";
import { useEffect, useState } from "react";

import { getSubjectInfo, type SubjectInfo } from "../api/staff";

const { Text } = Typography;

type Props = {
  token: string | null;
  convId: number;
};

/** 用户业务信息 + 客户端环境：admin 详情页右侧栏，调一次后端聚合端点。
 *  业务库未配置或拉取失败时 subject.found=false，仍展示 client_info。 */
export function SubjectInfoCard({ token, convId }: Props) {
  const [data, setData] = useState<SubjectInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

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

  return (
    <Card size="small" title="用户信息">
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
    </Card>
  );
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
