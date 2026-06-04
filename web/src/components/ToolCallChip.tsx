import { Check, Loader2, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "../lib/utils";
import type { ToolCallShown } from "../types";

function statusIcon(ok: boolean | undefined) {
  return ok === undefined ? Loader2 : ok ? Check : X;
}

// C/B 端聊天面（APP 内嵌 + BU 合作伙伴自助页）一律显示语言化进度，不暴露工具名/JSON。
// staff 后台用 EventBubble 不走此组件，调试需要的 raw 信息在那边。
export function ToolCallChip({ tc }: { tc: ToolCallShown; userType?: "c" | "b" }) {
  const { t } = useTranslation();
  const Icon = statusIcon(tc.ok);
  return (
    <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-sm bg-soft-brand border border-brand/20 text-brand text-body3">
      <Icon className={cn("h-3 w-3", tc.ok === undefined && "animate-spin")} />
      <span>{t(`chat.toolChip.${tc.name}`, { defaultValue: t("chat.toolChip.default") })}</span>
    </div>
  );
}
