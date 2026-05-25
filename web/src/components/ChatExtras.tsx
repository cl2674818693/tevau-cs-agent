/** ChatWindow 的辅助呈现块（拆出以控制单组件复杂度）。 */
import { useTranslation } from "react-i18next";

export function ChatHeader({
  mode,
  staffName,
  sending,
  onStop,
}: {
  mode: string;
  staffName?: string;
  sending: boolean;
  onStop: () => void;
}) {
  const { t } = useTranslation();
  return (
    <header className="safe-top sticky top-0 z-10 flex items-center px-page py-3 bg-surface-card border-b border-line">
      <div className="h-7 w-7 rounded bg-brand grid place-items-center mr-2">
        <span className="text-ink-primary text-body0 font-bold">T</span>
      </div>
      <div className="flex-1">
        <div className="text-sh3 text-ink-primary">{t("header.title")}</div>
        <div className="text-footnote text-ink-secondary">
          {mode === "human_takeover"
            ? t("header.staffMode", { name: staffName ?? "" })
            : t("header.aiMode")}
        </div>
      </div>
      {sending && (
        <button onClick={onStop} className="text-body2 text-ink-secondary px-2">
          {t("header.stop")}
        </button>
      )}
    </header>
  );
}

export function LoadingView() {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex h-full max-w-[720px] items-center justify-center text-ink-secondary">
      <div className="animate-pulse text-body2">{t("chat.loading")}</div>
    </div>
  );
}

export function ErrorView({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="mx-auto flex h-full max-w-[720px] flex-col items-center justify-center gap-3">
      <div className="text-body2 text-status-error">{t("chat.connectFailed")}</div>
      <button onClick={onRetry} className="rounded border border-line px-4 py-2 text-body2">
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
        <div className="px-page py-1.5 bg-status-warning/10 text-body3 text-status-warning text-center">
          {connection === "offline" ? t("chat.offline") : t("chat.reconnecting")}
        </div>
      )}
      {limitPct >= 80 && limitPct < 100 && (
        <div className="px-page py-1.5 bg-yellow-100 text-body3 text-yellow-800 text-center">
          {t("chat.quota", { pct: limitPct })}
        </div>
      )}
    </>
  );
}

export function Suggestions({ onPick }: { onPick: (q: string) => void }) {
  const { t } = useTranslation();
  const suggestions = t("chat.suggestions", { returnObjects: true }) as string[];
  return (
    <div className="px-page pb-2 flex flex-wrap gap-2">
      {suggestions.map((s) => (
        <button
          key={s}
          onClick={() => onPick(s)}
          className="rounded-full border border-line px-3 py-1.5 text-body3 text-ink-secondary hover:bg-surface-hover"
        >
          {s}
        </button>
      ))}
    </div>
  );
}
