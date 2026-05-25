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
        netError: "网络中断，请检查连接后重试。",
        suggestions: ["我的卡为什么被锁了？", "如何对接 Open API？", "查一下我最近的订单"],
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
        netError: "Network interrupted. Check your connection and retry.",
        suggestions: [
          "Why is my card locked?",
          "How do I integrate the Open API?",
          "Show my recent orders",
        ],
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
    detection: { order: ["querystring", "localStorage", "navigator"], caches: ["localStorage"] },
  });

// a11y：让 <html lang> 跟随当前语言，便于读屏软件用正确语音引擎
function syncHtmlLang(lng: string): void {
  if (typeof document !== "undefined") document.documentElement.lang = lng;
}
syncHtmlLang(i18n.language || "zh");
i18n.on("languageChanged", syncHtmlLang);

export default i18n;
