import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type ReportDef = {
  id: number;
  name: string;
  source: string;
  dims_json: string;
  filters_json: string;
  metrics_json: string;
  owner: string | null;
  created_at: string;
};

export type ReportResult = {
  sql: string;
  rows: Record<string, string | number | null>[];
};

export async function listReports(token: string): Promise<ReportDef[]> {
  const r = await staffFetch("/admin/api/v1/reports", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).definitions;
}

export async function createReport(
  token: string,
  body: {
    name: string;
    source: string;
    dims: string[];
    filters: { col: string; op: string; val: string | number }[];
    metrics: { op: string; col: string; alias: string }[];
  },
): Promise<{ id: number }> {
  const r = await staffFetch("/admin/api/v1/reports", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const b = await r.json().catch(() => ({}));
    throw new Error(b.detail ?? `create ${r.status}`);
  }
  return r.json();
}

export async function runReport(token: string, id: number): Promise<ReportResult> {
  const r = await staffFetch(`/admin/api/v1/reports/${id}/run`, {
    method: "POST",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`run ${r.status}`);
  return r.json();
}

export async function deleteReport(token: string, id: number): Promise<void> {
  const r = await staffFetch(`/admin/api/v1/reports/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`delete ${r.status}`);
}

export function exportCsvUrl(id: number): string {
  return `/admin/api/v1/reports/${id}/export.csv`;
}
