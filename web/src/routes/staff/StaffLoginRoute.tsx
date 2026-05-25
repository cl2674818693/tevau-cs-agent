import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { Field } from "../../components/ui/field";
import { Input } from "../../components/ui/input";
import { PageContainer } from "../../components/ui/page";
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
    <PageContainer width="narrow" center>
      <h2 className="mb-4 text-center text-sh1 text-ink-primary">客服工作台登录</h2>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field>
          <Input value={staffId} onChange={(e) => setStaffId(e.target.value)} placeholder="工号" />
        </Field>
        <Field error={err}>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="密码"
          />
        </Field>
        <Button type="submit" disabled={loading || !staffId.trim() || !password}>
          {loading ? "..." : "登录"}
        </Button>
      </form>
    </PageContainer>
  );
}
