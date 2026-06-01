import type { ColumnDef } from "@tanstack/react-table";
import { Download } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import {
  deleteReport,
  exportCsvUrl,
  listReports,
  runReport,
  type ReportDef,
  type ReportResult,
} from "../../api/adminReports";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card, CardContent } from "../../components/ui/card";
import { DatePicker } from "../../components/ui/date-picker";
import { PageContainer, PageHeader } from "../../components/ui/page";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../../components/ui/select";
import { Skeleton } from "../../components/ui/skeleton";
import { useStaffSession } from "../../hooks/useStaffSession";
import { useEffect } from "react";

// ── Loading skeleton ─────────────────────────────────────────────────────────

function SkeletonRows() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-md" />
      ))}
    </div>
  );
}

// ── Dynamic result columns ───────────────────────────────────────────────────

function buildResultColumns(
  cols: string[],
): ColumnDef<Record<string, string | number | null>>[] {
  return cols.map((c) => ({
    accessorKey: c,
    header: c,
    cell: ({ row }) => String(row.original[c] ?? ""),
    enableSorting: false,
  }));
}

// ── Route ────────────────────────────────────────────────────────────────────

export function ReportsRoute() {
  const { token, role } = useStaffSession();
  const allowed =
    role === "supervisor" || role === "manager" || role === "admin";

  const [reports, setReports] = useState<ReportDef[]>([]);
  const [loadingDefs, setLoadingDefs] = useState(true);
  const [loadError, setLoadError] = useState("");

  // Query form state
  const [selectedId, setSelectedId] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<Date | undefined>();
  const [dateTo, setDateTo] = useState<Date | undefined>();

  // Result state
  const [result, setResult] = useState<ReportResult | null>(null);
  const [querying, setQuerying] = useState(false);
  const [resultColumns, setResultColumns] = useState<
    ColumnDef<Record<string, string | number | null>>[]
  >([]);

  function reload() {
    if (!token) return;
    setLoadingDefs(true);
    listReports(token)
      .then(setReports)
      .catch((e: unknown) =>
        setLoadError(e instanceof Error ? e.message : "加载报表列表失败"),
      )
      .finally(() => setLoadingDefs(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setLoadError("需要主管/管理层/管理员权限");
      setLoadingDefs(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role]);

  async function handleQuery() {
    if (!token || !selectedId) return;
    setQuerying(true);
    setResult(null);
    try {
      const res = await runReport(token, Number(selectedId));
      const cols = res.rows[0] ? Object.keys(res.rows[0]) : [];
      setResultColumns(buildResultColumns(cols));
      setResult(res);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "查询失败");
    } finally {
      setQuerying(false);
    }
  }

  function handleDownloadCsv() {
    if (!selectedId) return;
    window.open(exportCsvUrl(Number(selectedId)), "_blank", "noreferrer");
  }

  async function handleDelete(id: number, name: string) {
    if (!token) return;
    if (!confirm(`确认删除报表"${name}"？此操作不可撤销。`)) return;
    try {
      await deleteReport(token, id);
      toast.success("已删除");
      if (selectedId === String(id)) {
        setSelectedId("");
        setResult(null);
      }
      reload();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "删除失败");
    }
  }

  const hasResults = result !== null && result.rows.length > 0;

  return (
    <PageContainer width="wide">
      <PageHeader
        title="自定义报表"
        actions={
          <Button
            size="sm"
            variant="outline"
            disabled={!hasResults}
            onClick={handleDownloadCsv}
          >
            <Download className="mr-1.5 h-4 w-4" />
            下载 CSV
          </Button>
        }
      />

      {loadError && (
        <Alert variant="destructive" className="mb-4">
          {loadError}
        </Alert>
      )}

      {/* Query form */}
      {allowed && (
        <Card className="mb-4">
          <CardContent className="flex flex-wrap items-end gap-3 pt-4 pb-4">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">报表类型</span>
              <Select
                value={selectedId}
                onValueChange={setSelectedId}
                disabled={loadingDefs}
              >
                <SelectTrigger className="w-56">
                  <SelectValue placeholder="选择报表" />
                </SelectTrigger>
                <SelectContent>
                  {reports.map((d) => (
                    <SelectItem key={d.id} value={String(d.id)}>
                      {d.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">开始日期</span>
              <DatePicker
                date={dateFrom}
                onChange={setDateFrom}
                placeholder="开始日期"
              />
            </div>

            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">结束日期</span>
              <DatePicker
                date={dateTo}
                onChange={setDateTo}
                placeholder="结束日期"
              />
            </div>

            <Button
              size="sm"
              onClick={handleQuery}
              disabled={!selectedId || querying}
            >
              {querying ? "查询中…" : "查询"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {querying ? (
        <SkeletonRows />
      ) : result ? (
        <div className="space-y-2">
          <DataTable
            columns={resultColumns}
            data={result.rows}
            empty="无结果"
          />
          <p className="text-xs text-muted-foreground font-mono px-1">
            SQL: {result.sql}
          </p>
        </div>
      ) : null}

      {/* Report definitions list */}
      {allowed && !loadingDefs && reports.length > 0 && (
        <div className="mt-6">
          <p className="mb-2 text-sm font-medium text-muted-foreground">
            已保存的报表定义
          </p>
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    <th className="px-4 py-2 text-left font-normal">ID</th>
                    <th className="px-4 py-2 text-left font-normal">名称</th>
                    <th className="px-4 py-2 text-left font-normal">数据源</th>
                    <th className="px-4 py-2 text-left font-normal">
                      owner
                    </th>
                    <th className="px-4 py-2 text-left font-normal">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((d) => (
                    <tr key={d.id} className="border-b last:border-0">
                      <td className="px-4 py-2 text-muted-foreground">
                        {d.id}
                      </td>
                      <td className="px-4 py-2">{d.name}</td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {d.source}
                      </td>
                      <td className="px-4 py-2 text-muted-foreground">
                        {d.owner ?? "—"}
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex gap-3">
                          <button
                            className="text-primary hover:underline"
                            onClick={() => setSelectedId(String(d.id))}
                          >
                            选择
                          </button>
                          <a
                            className="text-primary hover:underline"
                            href={exportCsvUrl(d.id)}
                            target="_blank"
                            rel="noreferrer"
                          >
                            CSV
                          </a>
                          <button
                            className="text-destructive hover:underline"
                            onClick={() => handleDelete(d.id, d.name)}
                          >
                            删除
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </PageContainer>
  );
}
