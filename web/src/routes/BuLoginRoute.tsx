import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { setIdentity } from "../api/identity";
import { Button } from "../components/ui/button";
import { Field } from "../components/ui/field";
import { Input } from "../components/ui/input";
import { PageContainer } from "../components/ui/page";

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
      setIdentity({ kind: "b", buId: buId.trim() });
      nav("/");
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageContainer width="narrow" center>
      <div className="mb-4 text-center">
        <div className="mx-auto mb-2 grid h-10 w-10 place-items-center rounded bg-brand">
          <span className="text-sh1 font-bold text-ink-primary">T</span>
        </div>
        <h2 className="text-sh1 text-ink-primary">Tevau AI 客服</h2>
        <p className="text-body3 text-ink-secondary">合作伙伴技术支持</p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field error={err}>
          <Input
            value={buId}
            onChange={(e) => setBuId(e.target.value)}
            placeholder="主账户 ID / 租户 ID（例如 1011010000068）"
          />
        </Field>
        <Button type="submit" disabled={loading || !buId.trim()}>
          {loading ? "..." : "进入对话"}
        </Button>
      </form>
    </PageContainer>
  );
}
