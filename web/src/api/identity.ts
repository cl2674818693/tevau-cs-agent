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

/** 游客标识：localStorage 持久化的匿名 ID，用于未登录会话的限流隔离（X-Guest-ID）。 */
function guestId(): string {
  const KEY = "ai_engine_guest_id";
  try {
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = crypto?.randomUUID?.() ?? `g-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    return "anon";
  }
}

/**
 * 当前身份对应的鉴权头。拿不到登录身份（C 端无 token / B 端无 bu_id 且无 cookie）时
 * 降级为游客头 X-Guest-ID，让后端走匿名降级会话，不再因 401 卡死。
 * B 端已登录时 cookie 经 credentials:'include' 仍会带上，后端优先用它。
 */
export async function authHeaders(): Promise<Record<string, string>> {
  const guest = { "X-Guest-ID": guestId() };
  if (!_identity) return guest;
  if (_identity.kind === "b") {
    return _identity.buId ? { "X-BU-ID": _identity.buId } : guest;
  }
  const token = await _identity.getToken();
  return token ? { Authorization: `Bearer ${token}` } : guest;
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
