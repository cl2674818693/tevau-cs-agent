import { getKpi, type StaffKpi } from "../../api/staff";
import { Alert } from "../../components/ui/alert";
import { EmptyState } from "../../components/ui/empty-state";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { Table, TableScroll, TBody, Td, Th, THead, Tr } from "../../components/ui/table";
import { useAsyncData } from "../../hooks/useAsyncData";
import { useStaffSession } from "../../hooks/useStaffSession";

function fmtDuration(seconds: number): string {
  if (seconds <= 0) return "-";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}分${s}秒` : `${s}秒`;
}

export function KpiRoute() {
  const { token } = useStaffSession();
  const { data, loading, error } = useAsyncData(
    () => (token ? getKpi(token) : null),
    [token],
  );
  const rows: StaffKpi[] = data ?? [];

  return (
    <PageContainer width="wide">
      <PageHeader title="客服 KPI 看板" />
      {error && (
        <Alert variant="error" className="mb-2">
          {error}
        </Alert>
      )}
      {loading ? (
        <LoadingState />
      ) : rows.length === 0 ? (
        <EmptyState>暂无数据</EmptyState>
      ) : (
        <TableScroll>
          <Table className="min-w-[680px]">
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
                  <Td className="whitespace-nowrap">{r.staff_id}</Td>
                  <Td>{r.takeovers}</Td>
                  <Td>{r.resolved}</Td>
                  <Td>{r.releases}</Td>
                  <Td>{(r.release_ratio * 100).toFixed(0)}%</Td>
                  <Td>{(r.resolved_ratio * 100).toFixed(0)}%</Td>
                  <Td className="whitespace-nowrap">{fmtDuration(r.avg_handle_seconds)}</Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        </TableScroll>
      )}
    </PageContainer>
  );
}
