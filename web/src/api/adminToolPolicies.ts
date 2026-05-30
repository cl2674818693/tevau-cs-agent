import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type ToolPolicy = {
  tool_name: string;
  role: string;
  allowed: number;
  unmask_allowed: number;
  updated_by: string | null;
  updated_at: string;
};

export async function listToolPolicies(token: string): Promise<ToolPolicy[]> {
  const r = await staffFetch("/admin/api/v1/tool-policies", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`list ${r.status}`);
  return (await r.json()).items;
}

export async function upsertToolPolicies(
  token: string,
  items: { tool_name: string; role: string; allowed: number; unmask_allowed: number }[],
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/tool-policies", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({ items }),
  });
  if (!r.ok) throw new Error(`upsert ${r.status}`);
}

export const TOOL_NAMES: string[] = [
  "query_user",
  "query_card",
  "query_kyc",
  "query_balance",
  "query_transaction",
  "query_bu_user",
  "query_bu_order",
  "query_bu_request_log",
  "lookup_api_doc",
  "lookup_error_code",
  "search_code",
  "read_file",
];

export const POLICY_ROLES: string[] = ["agent", "senior", "engineer", "supervisor", "ai"];
