import { Wifi } from "lucide-react";
/** ChatWindow 的辅助呈现块（拆出以控制单组件复杂度）。 */
import { useTranslation } from "react-i18next";

import { LanguageSwitcher } from "./LanguageSwitcher";

export function ChatHeader({
  mode,
  staffName,
  sending,
  onStop,
  userType,
}: {
  mode: string;
  staffName?: string;
  sending: boolean;
  onStop: () => void;
  // C 端 webview 由 APP bridge 强制同步语言，不展示切换器；B 端浏览器显示。
  userType: "c" | "b";
}) {
  const { t } = useTranslation();
  // human_pending：橙色点 + 等待文案，让刷新后用户仍能看到自己在排队（事件触发的临时气泡不回放）。
  // human_takeover：隐藏状态点，文案带客服名。其余（ai / ai_draft）维持原 AI 模式。
  const subtitle =
    mode === "human_takeover"
      ? t("header.staffMode", { name: staffName ?? "" })
      : mode === "human_pending"
        ? t("header.pendingMode")
        : t("header.aiMode");
  const dotClass =
    mode === "human_pending" ? "bg-status-warning" : "bg-status-success";
  return (
    <header className="safe-top sticky top-0 z-10 flex items-center justify-between px-page py-3 bg-surface-card border-b border-line">
      <div className="flex items-center gap-3">
        <div className="h-9 w-9 rounded-md grid place-items-center bg-brand">
          <span className="text-ink-onbrand font-bold text-body0">T</span>
        </div>
        <div className="flex flex-col">
          <div className="text-sh3 font-bold text-ink-primary leading-none">{t("header.title")}</div>
          <div className="flex items-center gap-1.5 mt-1">
            {mode !== "human_takeover" && (
              <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
            )}
            <span className="text-footnote text-ink-secondary">{subtitle}</span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {userType === "b" && <LanguageSwitcher size="small" />}
        {sending && (
          <button
            onClick={onStop}
            className="px-3 py-1.5 rounded text-body3 text-ink-secondary border border-line hover:bg-surface-hover transition-colors"
          >
            {t("header.stop")}
          </button>
        )}
      </div>
    </header>
  );
}

/**
 * 游客（未登录）登录引导条。区分两类登录路径：
 * - C 端 APP 用户：在 APP 内登录（浏览器无法代办，仅提示）
 * - B 端合作伙伴：用主账户 ID 在浏览器登录 → /bu/login
 * 空状态与已开始对话两种状态下都常驻可见，避免「只在 APP 内登录」误导 B 端。
 */
export function GuestLoginBar() {
  const { t } = useTranslation();
  return (
    <div className="px-page py-2 bg-soft-brand border-b border-line text-footnote text-ink-secondary text-center leading-relaxed">
      {t("chat.guestBarText")}
      <a href="/bu/login" className="ml-1 font-bold text-brand hover:underline">
        {t("chat.guestBarLink")}
      </a>
    </div>
  );
}

export function EmptyState({ userType }: { userType: "c" | "b" | "g" }) {
  const { t } = useTranslation();
  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center px-8 gap-3">
      <div className="h-14 w-14 rounded-xl grid place-items-center bg-soft-brand">
        <span className="text-brand font-bold text-h2">T</span>
      </div>
      <div className="text-sh1 font-bold text-ink-primary">{t("chat.emptyTitle")}</div>
      <p className="text-body2 text-ink-secondary leading-relaxed max-w-[320px]">
        {t(`chat.emptyHint.${userType}`)}
      </p>
    </div>
  );
}

export function LoadingView() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex h-full max-w-[720px] items-center justify-center bg-surface-page text-ink-secondary">
      <div className="animate-pulse text-body2">{t("chat.loading")}</div>
    </div>
  );
}

export function ErrorView({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex h-full max-w-[720px] flex-col items-center justify-center gap-3 bg-surface-page">
      <div className="text-body2 text-status-error">{t("chat.connectFailed")}</div>
      <button
        onClick={onRetry}
        className="rounded border border-line px-4 py-2 text-body2 text-brand hover:bg-soft-brand transition-colors"
      >
        {t("chat.retry")}
      </button>
    </div>
  );
}

export function StatusBanners({
  connection,
  limitPct,
}: {
  connection: "online" | "offline" | "reconnecting";
  limitPct: number;
}) {
  const { t } = useTranslation();
  return (
    <>
      {connection !== "online" && (
        <div className="flex items-center justify-center gap-1.5 px-page py-1.5 bg-soft-warning border-b border-status-warning/30 text-body3 text-status-warning text-center">
          <Wifi className="h-3.5 w-3.5" />
          {connection === "offline" ? t("chat.offline") : t("chat.reconnecting")}
        </div>
      )}
      {limitPct >= 80 && limitPct < 100 && (
        <div className="px-page py-1.5 bg-soft-warning text-body3 text-status-warning text-center">
          {t("chat.quota", { pct: limitPct })}
        </div>
      )}
    </>
  );
}
