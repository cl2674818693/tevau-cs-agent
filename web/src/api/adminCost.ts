import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type UsageItem = {
  model: string;
  input_tokens: number;
  output_tokens: number;
  currency?: string | null;
  input_cost?: number;
  output_cost?: number;
  total_cost?: number;
};

export type Pricing = {
  model: string;
  input_price_per_1k_x10000: number;
  output_price_per_1k_x10000: number;
  currency: string;
  updated_at: string;
};

export async function getUsage(
  token: string,
  opts?: { from?: string; to?: string; user_type?: string; with_cost?: boolean },
): Promise<UsageItem[]> {
  const qs = new URLSearchParams();
  if (opts?.from) qs.set("from", opts.from);
  if (opts?.to) qs.set("to", opts.to);
  if (opts?.user_type) qs.set("user_type", opts.user_type);
  if (opts?.with_cost) qs.set("with_cost", "true");
  const r = await staffFetch(`/admin/api/v1/cost/usage?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`usage ${r.status}`);
  return (await r.json()).items;
}

export async function listPricing(token: string): Promise<Pricing[]> {
  const r = await staffFetch("/admin/api/v1/cost/pricing", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`pricing ${r.status}`);
  return (await r.json()).items;
}

export async function upsertPricing(
  token: string,
  body: {
    model: string;
    input_price_per_1k_x10000: number;
    output_price_per_1k_x10000: number;
    currency: string;
  },
): Promise<void> {
  const r = await staffFetch("/admin/api/v1/cost/pricing", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`upsert pricing ${r.status}`);
}
