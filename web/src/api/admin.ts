import { staffFetch } from "./staffFetch";

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export type PromptVersions = {
  versions: string[];
  default: string;
  rollout: Record<string, number>;
};

export async function getPromptVersions(token: string): Promise<PromptVersions> {
  const r = await staffFetch("/admin/api/v1/prompts/versions", { headers: authHeaders(token) });
  if (!r.ok) throw new Error(`versions failed ${r.status}`);
  return r.json();
}

export type PromptAbStat = {
  version: string;
  assistant_turns: number;
  failed: number;
  failed_rate: number;
  downvote: number;
  downvote_rate: number;
};

export type PromptAbStatsResult = {
  from: string;
  to: string;
  versions: PromptAbStat[];
};

export async function getPromptAbStats(
  token: string,
  opts?: { from?: string; to?: string },
): Promise<PromptAbStatsResult> {
  const qs = new URLSearchParams();
  if (opts?.from) qs.set("from", opts.from);
  if (opts?.to) qs.set("to", opts.to);
  const r = await staffFetch(`/admin/api/v1/prompts/ab-stats?${qs.toString()}`, {
    headers: authHeaders(token),
  });
  if (!r.ok) throw new Error(`ab-stats failed ${r.status}`);
  const j = await r.json();
  return { ...j, versions: j.versions ?? [] };
}

/** 保存灰度比例并触发后端热加载。返回 ok 与新 rollout，或抛错带后端校验信息。 */
export async function setRollout(
  token: string,
  rollout: Record<string, number>,
): Promise<Record<string, number>> {
  const r = await staffFetch("/admin/api/v1/prompts/rollout", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ rollout }),
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail ?? `save failed ${r.status}`);
  }
  const body = await r.json();
  return body.rollout as Record<string, number>;
}
