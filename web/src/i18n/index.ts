import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

// 仅覆盖 C/B 客户面（真实用户）。staff/admin 内部工具为中文母语员工使用，不做国际化。
const resources = {
  zh: {
    translation: {
      header: {
        title: "Tevau AI 客服",
        staffMode: "客服 {{name}} · 已认证",
        aiMode: "由 AI 驱动 · 复杂问题转人工",
        pendingMode: "等待人工客服接入…",
        stop: "停止生成",
      },
      chat: {
        loading: "正在连接 Tevau AI 客服…",
        connectFailed: "连接失败，请检查网络后重试。",
        retry: "重试",
        offline: "网络已断开，正在等待重新连接…",
        reconnecting: "正在重新连接…",
        quota: "您今日用量已达 {{pct}}%，建议核心问题尽快咨询。",
        thinking: "思考中…",
        inputPlaceholder: "描述你的问题…",
        inputRateLimited: "请求过于频繁，请稍后再试…",
        inputHumanMode: "向客服留言…",
        messageLog: "对话消息",
        send: "发送",
        handoff: "没解决？转人工 →",
        agentBadge: "客服 {{name}} · 已认证",
        agentAvatar: "客",
        agentLabel: "客服",
        agentVerified: "已认证",
        netError: "网络中断，请检查连接后重试。",
        feedbackUp: "有帮助",
        feedbackDown: "没帮助",
        feedbackThanks: "感谢反馈",
        suggestions: ["我的卡为什么被锁了？", "如何对接 Open API？", "查一下我最近的订单"],
        emptyTitle: "你好，我是 Tevau 助手",
        guestBarText: "查询账户、卡片或交易需登录：APP 用户请在 APP 内登录；合作伙伴可",
        guestBarLink: "主账户登录",
        toolChip: {
          query_user: "正在查询账户信息…",
          query_card: "正在查询卡片状态…",
          query_balance: "正在查询余额…",
          query_kyc: "正在查询认证状态…",
          query_transaction: "正在查询交易记录…",
          query_bu_order: "正在查询订单…",
          query_bu_request_log: "正在查询接口调用记录…",
          search_code: "正在排查问题…",
          read_file: "正在排查问题…",
          lookup_api_doc: "正在查阅接口文档…",
          create_ticket: "正在为您创建工单…",
          default: "正在为您处理…",
        },
      },
      ticket: {
        assigned: "工单已受理",
        in_progress: "工单处理中",
        escalated: "工单已升级",
        resolved: "工单已解决",
        closed: "工单已关闭",
        reopen: "工单已重开",
        cardSummaryFallback: "您的工单进展",
      },
      error: {
        title: "页面出错了",
        detail: "请刷新页面重试。若反复出现，请联系客服。",
        reload: "刷新页面",
      },
    },
  },
  en: {
    translation: {
      header: {
        title: "Tevau AI Support",
        staffMode: "Agent {{name}} · Verified",
        aiMode: "AI-powered · Escalate to human for complex issues",
        pendingMode: "Waiting for an agent…",
        stop: "Stop",
      },
      chat: {
        loading: "Connecting to Tevau AI Support…",
        connectFailed: "Connection failed. Check your network and retry.",
        retry: "Retry",
        offline: "Offline. Waiting to reconnect…",
        reconnecting: "Reconnecting…",
        quota: "You've used {{pct}}% of today's quota. Prioritize key questions.",
        thinking: "Thinking…",
        inputPlaceholder: "Describe your issue…",
        inputRateLimited: "Too many requests. Please try again later…",
        inputHumanMode: "Message an agent…",
        messageLog: "Conversation messages",
        send: "Send",
        handoff: "Not resolved? Talk to a human →",
        agentBadge: "Agent {{name}} · Verified",
        agentAvatar: "A",
        agentLabel: "Agent",
        agentVerified: "Verified",
        netError: "Network interrupted. Check your connection and retry.",
        feedbackUp: "Helpful",
        feedbackDown: "Not helpful",
        feedbackThanks: "Thanks for the feedback",
        suggestions: [
          "Why is my card locked?",
          "How do I integrate the Open API?",
          "Show my recent orders",
        ],
        emptyTitle: "Hi, I'm the Tevau assistant",
        guestBarText:
          "Sign in to view accounts, cards or transactions: app users please sign in inside the app; partners can",
        guestBarLink: "sign in with main account",
        toolChip: {
          query_user: "Looking up account info…",
          query_card: "Checking card status…",
          query_balance: "Checking balance…",
          query_kyc: "Checking verification status…",
          query_transaction: "Looking up transactions…",
          query_bu_order: "Looking up orders…",
          query_bu_request_log: "Looking up API call logs…",
          search_code: "Investigating the issue…",
          read_file: "Investigating the issue…",
          lookup_api_doc: "Checking the API docs…",
          create_ticket: "Creating a ticket for you…",
          default: "Working on it…",
        },
      },
      ticket: {
        assigned: "Ticket accepted",
        in_progress: "Ticket in progress",
        escalated: "Ticket escalated",
        resolved: "Ticket resolved",
        closed: "Ticket closed",
        reopen: "Ticket reopened",
        cardSummaryFallback: "Your ticket progress",
      },
      error: {
        title: "Something went wrong",
        detail: "Please refresh. If it keeps happening, contact support.",
        reload: "Refresh",
      },
    },
  },
};

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: "zh",
    supportedLngs: ["zh", "en"],
    interpolation: { escapeValue: false },
    // 外壳语言不再跟随浏览器/设备（navigator）：C 端 webview 由 APP 经 bridge 决定
    // （syncLanguageFromBridge），B 端浏览器无 bridge/无 ?lng/无缓存时回退 fallbackLng=zh。
    detection: { order: ["querystring", "localStorage"], caches: ["localStorage"] },
  });

// a11y：让 <html lang> 跟随当前语言，便于读屏软件用正确语音引擎
function syncHtmlLang(lng: string): void {
  if (typeof document !== "undefined") document.documentElement.lang = lng;
}
syncHtmlLang(i18n.language || "zh");
i18n.on("languageChanged", syncHtmlLang);

/**
 * C 端 webview：外壳语言跟随 APP 当前语言（bridge.getEnv().language，APP 取值 'en'/'zh-Hant'）。
 * 归一到 i18n 支持的 zh/en。URL 显式 ?lng 优先，不被 APP 覆盖（便于调试/指定）。
 * B 端浏览器无 bridge → getEnv 取不到 language → 不改，沿用 ?lng/localStorage/fallbackLng(zh)。
 */
export async function syncLanguageFromBridge(): Promise<void> {
  if (typeof location !== "undefined" && new URLSearchParams(location.search).get("lng")) return;
  const { bridge } = await import("../hooks/useAppBridge");
  const raw = (await bridge.getEnv()).language;
  if (!raw) return;
  const lng = raw.toLowerCase().startsWith("zh") ? "zh" : "en";
  if (i18n.language !== lng) await i18n.changeLanguage(lng);
}

export default i18n;
