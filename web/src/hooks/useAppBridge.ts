import { useEffect, useState } from "react";

declare global {
  interface Window {
    // C 端 APP（Flutter）通过 JS Bridge 注入 JWT（spec §4.1.1）
    aiEngineSetToken?: (token: string) => void;
    aiEngineRequestToken?: () => void;
  }
}

/**
 * C 端 JS Bridge：等 APP 注入 JWT。返回 null 表示尚未注入（B 端浏览器场景永远 null）。
 * 真实接入（验签公钥 + claims 格式）在 task-05；本 hook 只负责前端拿 token。
 */
export function useAppBridge(): string | null {
  const [jwt, setJwt] = useState<string | null>(null);
  useEffect(() => {
    window.aiEngineSetToken = (token: string) => setJwt(token);
    window.aiEngineRequestToken?.(); // APP 实现此回调来注入 JWT
    return () => {
      delete window.aiEngineSetToken;
    };
  }, []);
  return jwt;
}
