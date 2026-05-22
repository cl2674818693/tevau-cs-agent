/**
 * 前端会话身份（spec §4.1）。集中管理鉴权头：
 * - C 端 APP：Authorization: Bearer <JWT>（bridge.getToken 注入，不进 URL/历史）
 * - B 端浏览器：登录后 session cookie（fetch credentials:'include' 自动带），dev 回退 X-BU-ID
 */

export type Identity =
  | { kind: "c"; getToken: () => Promise<string | null> }
  | { kind: "b"; buId?: string };

let _identity: Identity | null = null;

export function setIdentity(id: Identity): void {
  _identity = id;
}

export function getIdentity(): Identity | null {
  return _identity;
}

export function userType(): "c" | "b" {
  return _identity?.kind === "c" ? "c" : "b";
}

/** 当前身份对应的鉴权头。C 端取 token 失败抛 AuthExpiredError（caller 触发续签）。 */
export async function authHeaders(): Promise<Record<string, string>> {
  if (!_identity) return {};
  if (_identity.kind === "b") {
    return _identity.buId ? { "X-BU-ID": _identity.buId } : {};
  }
  const token = await _identity.getToken();
  if (!token) throw new AuthExpiredError();
  return { Authorization: `Bearer ${token}` };
}

export class AuthExpiredError extends Error {
  constructor() {
    super("auth expired");
    this.name = "AuthExpiredError";
  }
}

/**
 * 启动时确定身份：bridge 就绪 → C 端（Bearer）；否则 B 端（cookie，dev 回退 ?bu_id）。
 * 已显式 setIdentity（如 B 端登录页）则沿用。
 */
function bridgePresent(): boolean {
  return typeof window !== "undefined" && !!window.flutter_inappwebview?.callHandler;
}

async function isCSide(url: URLSearchParams): Promise<boolean> {
  if (url.get("token")) return true;
  // 仅在「像 APP 环境」时才等 bridge 注入（冷启动竞态）；B 端浏览器立即返回，不阻塞 5s。
  if (!bridgePresent() && url.get("env") !== "app") return false;
  const { bridge } = await import("../hooks/useAppBridge");
  return bridgePresent() || (await bridge.whenReady());
}

export async function resolveIdentity(): Promise<Identity> {
  if (_identity) return _identity;
  const url = new URLSearchParams(typeof location !== "undefined" ? location.search : "");
  if (await isCSide(url)) {
    const { bridge } = await import("../hooks/useAppBridge");
    _identity = { kind: "c", getToken: () => bridge.getToken() };
  } else {
    _identity = { kind: "b", buId: url.get("bu_id") ?? undefined };
  }
  return _identity;
}
