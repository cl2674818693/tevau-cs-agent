import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../components/ui/button";

/** B 端主账户 ID 登录页（spec §4.1）。后端 /api/v1/auth/bu/login 在 task-04 落地。 */
export function BuLoginRoute() {
  const [buId, setBuId] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      const r = await fetch("/api/v1/auth/bu/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bu_id: buId.trim() }),
      });
      if (!r.ok) {
        setErr((await r.text()) || "主账户不存在或已禁用");
        return;
      }
      nav("/");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-[420px] flex-col justify-center px-page gap-4">
      <div className="text-center">
        <div className="mx-auto mb-2 h-10 w-10 rounded bg-brand grid place-items-center">
          <span className="text-ink-primary text-sh1 font-bold">T</span>
        </div>
        <h2 className="text-sh1 text-ink-primary">Tevau AI 客服</h2>
        <p className="text-body3 text-ink-secondary">合作伙伴技术支持</p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input
          value={buId}
          onChange={(e) => setBuId(e.target.value)}
          placeholder="主账户 ID（例如 BU00243780）"
          className="focus-glow rounded border border-line px-input-x py-3 text-body1 outline-none transition-all duration-250"
        />
        <Button type="submit" disabled={loading || !buId.trim()}>
          {loading ? "..." : "进入对话"}
        </Button>
        {err && <div className="text-body3 text-status-error">{err}</div>}
      </form>
    </div>
  );
}
