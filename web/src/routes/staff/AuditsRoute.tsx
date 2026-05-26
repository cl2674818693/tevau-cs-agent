import { useState } from "react";
import { Link } from "react-router-dom";

import { getRecentAudits } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { Badge } from "../../components/ui/badge";
import { EmptyState } from "../../components/ui/empty-state";
import { FilterTabs } from "../../components/ui/filter-tabs";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { Table, TableScroll, TBody, Td, Th, THead, Tr } from "../../components/ui/table";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

const FILTER_OPTIONS = [
  { value: "all", label: "全部" },
  { value: "rejected", label: "只看被拒" },
];

export function AuditsRoute() {
  const { token } = useStaffSession();
  const [filter, setFilter] = useState("all");
  const rejectedOnly = filter === "rejected";
  const { data, loading, error } = useAsyncData(
    () => (token ? getRecentAudits(token, rejectedOnly) : null),
    [token, rejectedOnly],
  );
  const rows = data ?? [];

  return (
    <PageContainer width="wide">
      <PageHeader title="全局工具审计" />
      <FilterTabs className="mb-3" value={filter} onChange={setFilter} options={FILTER_OPTIONS} />
      {error && (
        <Alert variant="error" className="mb-2">
          {error}
        </Alert>
      )}
      {loading ? (
        <LoadingState />
      ) : rows.length === 0 ? (
        <EmptyState>暂无记录</EmptyState>
      ) : (
        <TableScroll>
          <Table className="min-w-[640px]">
            <THead>
              <tr>
                <Th>时间</Th>
                <Th>会话</Th>
                <Th>工具</Th>
                <Th>耗时</Th>
                <Th>状态</Th>
              </tr>
            </THead>
            <TBody>
              {rows.map((a) => (
                <Tr key={a.id} className="align-top">
                  <Td className="whitespace-nowrap">{a.created_at}</Td>
                  <Td>
                    <Link to={`/staff/conversations/${a.conversation_id}/logs`} className="text-brand">
                      #{a.conversation_id}
                    </Link>
                  </Td>
                  <Td className="whitespace-nowrap">{a.tool_name}</Td>
                  <Td className="whitespace-nowrap">{a.duration_ms}ms</Td>
                  <Td>
                    {a.rejected ? (
                      <Badge variant="error">被拒：{a.reject_reason ?? "-"}</Badge>
                    ) : (
                      <Badge variant="success">ok</Badge>
                    )}
                  </Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        </TableScroll>
      )}
      <p className="mt-3 text-footnote text-ink-secondary">仅显示最近 100 条。</p>
    </PageContainer>
  );
}
