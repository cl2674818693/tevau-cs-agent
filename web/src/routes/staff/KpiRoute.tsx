import { useEffect, useState } from "react";

import { getKpi, type StaffKpi } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { EmptyState } from "../../components/ui/empty-state";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Table, TBody, Td, Th, THead, Tr } from "../../components/ui/table";
import { useStaffSession } from "../../hooks/useStaffSession";

function fmtDuration(seconds: number): string {
  if (seconds <= 0) return "-";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}分${s}秒` : `${s}秒`;
}

export function KpiRoute() {
  const { token } = useStaffSession();
  const [rows, setRows] = useState<StaffKpi[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!token) return;
    getKpi(token)
      .then(setRows)
      .catch(() => setErr("加载失败"));
  }, [token]);

  return (
    <PageContainer>
      <PageHeader title="客服 KPI 看板" />
      {err && (
        <Alert variant="error" className="mb-2">
          {err}
        </Alert>
      )}
      <Table>
        <THead>
          <tr>
            <Th>客服</Th>
            <Th>接管</Th>
            <Th>解决</Th>
            <Th>释放回 AI</Th>
            <Th>释放率</Th>
            <Th>解决率</Th>
            <Th>平均时长</Th>
          </tr>
        </THead>
        <TBody>
          {rows.map((r) => (
            <Tr key={r.staff_id}>
              <Td>{r.staff_id}</Td>
              <Td>{r.takeovers}</Td>
              <Td>{r.resolved}</Td>
              <Td>{r.releases}</Td>
              <Td>{(r.release_ratio * 100).toFixed(0)}%</Td>
              <Td>{(r.resolved_ratio * 100).toFixed(0)}%</Td>
              <Td>{fmtDuration(r.avg_handle_seconds)}</Td>
            </Tr>
          ))}
        </TBody>
      </Table>
      {rows.length === 0 && !err && <EmptyState>暂无数据</EmptyState>}
    </PageContainer>
  );
}
