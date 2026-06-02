// 客服 session 辅助：直接往 localStorage 写一个能解出 sub/role 的合法 JWT。
// JWT payload base64url：去掉 padding 的 +/ 换成 -_。

function b64url(s: string): string {
  return Buffer.from(s, "utf8")
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

/** 生成一个含 sub/role 的"够用"JWT（签名段填 'x'，仅供前端 atob 解码使用）。 */
export function buildStaffJwt(staffId: string, role: string): string {
  const header = b64url(JSON.stringify({ alg: "none", typ: "JWT" }));
  const payload = b64url(JSON.stringify({ sub: staffId, role }));
  return `${header}.${payload}.x`;
}

export function loginAsStaff(staffId = "s_alice", role = "agent"): string {
  const token = buildStaffJwt(staffId, role);
  localStorage.setItem("staff_jwt", token);
  return token;
}

export function logoutStaff(): void {
  localStorage.removeItem("staff_jwt");
}
