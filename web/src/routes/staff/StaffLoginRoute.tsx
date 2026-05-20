import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { useStaffSession } from "../../hooks/useStaffSession";
import { staffLogin } from "../../api/staff";

export function StaffLoginRoute() {
  const [staffId, setStaffId] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useStaffSession();
  const nav = useNavigate();

  async function submit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr("");
    try {
      const { token } = await staffLogin(staffId.trim(), password);
      login(token);
      nav("/staff/conversations");
    } catch {
      setErr("工号或密码错误");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-[420px] flex-col justify-center px-page gap-4">
      <h2 className="text-sh1 text-ink-primary text-center">客服工作台登录</h2>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input
          value={staffId}
          onChange={(e) => setStaffId(e.target.value)}
          placeholder="工号"
          className="focus-glow rounded border border-line px-input-x py-3 text-body1 outline-none"
        />
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="密码"
          className="focus-glow rounded border border-line px-input-x py-3 text-body1 outline-none"
        />
        <Button type="submit" disabled={loading || !staffId.trim() || !password}>
          {loading ? "..." : "登录"}
        </Button>
        {err && <div className="text-body3 text-status-error">{err}</div>}
      </form>
    </div>
  );
}
