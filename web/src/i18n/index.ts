import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

// 仅覆盖 C/B 客户面（真实用户）。staff/admin 内部工具为中文母语员工使用，不做国际化。
// zh 资源走「繁体中文（台湾用语）」：title 文案统一台湾用法（連線/網路/介面/文件/回饋/聯絡），LANGUAGE_NATIVE.zh = "中文繁體"。
const resources = {
  zh: {
    translation: {
      header: {
        title: "Tevau AI 客服",
        staffMode: "客服 {{name}} · 已認證",
        aiMode: "由 AI 驅動 · 複雜問題轉接人工",
        pendingMode: "已為您建立工單，等候人工客服",
        stop: "停止生成",
      },
      chat: {
        loading: "正在連線 Tevau AI 客服…",
        connectFailed: "連線失敗，請檢查網路後重試。",
        retry: "重試",
        offline: "網路已中斷，正在等待重新連線…",
        reconnecting: "正在重新連線…",
        quota: "您今日用量已達 {{pct}}%，建議優先諮詢核心問題。",
        thinking: "思考中…",
        inputPlaceholder: "描述您的問題…",
        inputRateLimited: "請求過於頻繁，請稍後再試…",
        inputHumanMode: "繼續補充資訊，客服上線後會看到…",
        messageLog: "對話訊息",
        send: "傳送",
        handoff: "尚未解決？轉接人工 →",
        agentBadge: "客服 {{name}} · 已認證",
        agentAvatar: "客",
        agentLabel: "客服",
        agentVerified: "已認證",
        netError: "網路中斷，請檢查連線後重試。",
        feedbackUp: "有幫助",
        feedbackDown: "沒幫助",
        feedbackThanks: "感謝您的回饋",
        suggestions: ["我的卡為什麼被鎖了？", "如何串接 Open API？", "查一下我最近的訂單"],
        emptyTitle: "您好，我是 Tevau 助理",
        guestBarText: "查詢帳戶、卡片或交易需登入：APP 使用者請在 APP 內登入；合作夥伴可",
        guestBarLink: "主帳戶登入",
        toolChip: {
          query_user: "正在查詢帳戶資訊…",
          query_card: "正在查詢卡片狀態…",
          query_balance: "正在查詢餘額…",
          query_kyc: "正在查詢認證狀態…",
          query_transaction: "正在查詢交易紀錄…",
          query_bu_order: "正在查詢訂單…",
          query_bu_request_log: "正在查詢介面呼叫紀錄…",
          query_bu_card: "正在查詢卡片資訊…",
          query_bu_user: "正在查詢使用者資訊…",
          lookup_error_code: "正在查詢錯誤碼…",
          search_code: "正在排查問題…",
          read_file: "正在排查問題…",
          lookup_api_doc: "正在查閱介面文件…",
          create_ticket: "正在為您建立工單…",
          default: "正在為您處理…",
        },
      },
      ticket: {
        assigned: "工單已受理",
        in_progress: "工單處理中",
        escalated: "工單已升級",
        resolved: "工單已解決",
        closed: "工單已關閉",
        reopen: "工單已重開",
        cardSummaryFallback: "您的工單進度",
      },
      error: {
        title: "頁面發生錯誤",
        detail: "請重新整理頁面再試。若反覆出現，請聯絡客服。",
        reload: "重新整理頁面",
      },
      buLogin: {
        title: "Tevau AI 客服",
        subtitle: "合作夥伴技術支援",
        idLabel: "主帳戶 ID",
        idRequired: "請輸入主帳戶 ID",
        idPlaceholder: "主帳戶 ID / 租戶 ID（例如 1011010000068）",
        submit: "進入對話",
        notFound: "主帳戶不存在或已停用",
      },
    },
  },
  en: {
    translation: {
      header: {
        title: "Tevau AI Support",
        staffMode: "Agent {{name}} · Verified",
        aiMode: "AI-powered · Escalate to human for complex issues",
        pendingMode: "Ticket created · waiting for an agent",
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
        inputHumanMode: "Add details — an agent will see them when online…",
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
          query_bu_card: "Looking up card info…",
          query_bu_user: "Looking up user info…",
          lookup_error_code: "Looking up error codes…",
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
      buLogin: {
        title: "Tevau AI Support",
        subtitle: "Partner technical support",
        idLabel: "Main account ID",
        idRequired: "Please enter your main account ID",
        idPlaceholder: "Main account / tenant ID (e.g. 1011010000068)",
        submit: "Enter chat",
        notFound: "Account not found or disabled",
      },
    },
  },
};

// 12 语言对齐 APP（Flutter lib/l10n/）：ar/en/es/id/ja/ko/pt/ru/th/tr/vi/zh。
// chat.* 只翻"首屏"和"转人工提示"四个高频 key，其余靠 fallback=en。
// buLogin.* 整套全翻——B 端 LanguageSwitcher 允许用户随意切，缺译会让"切到 ja 仍是英文"。
// 跨端策略：后端 SSE/greeting/refusal 走 server/src/ai_engine/i18n/messages.py；前端 UI 走此处。
type BuLoginEntries = {
  title: string;
  subtitle: string;
  idLabel: string;
  idRequired: string;
  idPlaceholder: string;
  submit: string;
  notFound: string;
};
type LangExtras = {
  emptyTitle?: string;
  handoff?: string;
  thinking?: string;
  send?: string;
  buLogin: BuLoginEntries;
};
const _criticalKeys = (vals: LangExtras) => ({
  translation: {
    chat: {
      emptyTitle: vals.emptyTitle ?? "Hi, I'm the Tevau assistant",
      handoff: vals.handoff ?? "Not resolved? Talk to a human →",
      thinking: vals.thinking ?? "Thinking…",
      send: vals.send ?? "Send",
    },
    buLogin: vals.buLogin,
  },
});

const extra: Record<string, LangExtras> = {
  ar: {
    emptyTitle: "مرحباً، أنا مساعد Tevau",
    handoff: "لم يُحل؟ تواصل مع موظف →",
    thinking: "جاري التفكير...",
    send: "إرسال",
    buLogin: {
      title: "دعم Tevau AI",
      subtitle: "الدعم الفني للشركاء",
      idLabel: "معرّف الحساب الرئيسي",
      idRequired: "يرجى إدخال معرّف الحساب الرئيسي",
      idPlaceholder: "معرّف الحساب الرئيسي / المستأجر (مثال: 1011010000068)",
      submit: "بدء المحادثة",
      notFound: "الحساب غير موجود أو معطّل",
    },
  },
  es: {
    emptyTitle: "Hola, soy el asistente de Tevau",
    handoff: "¿No resuelto? Habla con un agente →",
    thinking: "Pensando…",
    send: "Enviar",
    buLogin: {
      title: "Soporte Tevau AI",
      subtitle: "Soporte técnico para socios",
      idLabel: "ID de cuenta principal",
      idRequired: "Por favor ingresa tu ID de cuenta principal",
      idPlaceholder: "ID de cuenta principal / inquilino (p. ej. 1011010000068)",
      submit: "Entrar al chat",
      notFound: "Cuenta no encontrada o deshabilitada",
    },
  },
  id: {
    emptyTitle: "Halo, saya asisten Tevau",
    handoff: "Belum selesai? Bicara dengan agen →",
    thinking: "Berpikir…",
    send: "Kirim",
    buLogin: {
      title: "Dukungan Tevau AI",
      subtitle: "Dukungan teknis mitra",
      idLabel: "ID akun utama",
      idRequired: "Silakan masukkan ID akun utama Anda",
      idPlaceholder: "ID akun utama / tenant (mis. 1011010000068)",
      submit: "Mulai obrolan",
      notFound: "Akun tidak ditemukan atau dinonaktifkan",
    },
  },
  ja: {
    emptyTitle: "こんにちは、Tevau アシスタントです",
    handoff: "解決しない場合は担当者へ →",
    thinking: "考え中…",
    send: "送信",
    buLogin: {
      title: "Tevau AI サポート",
      subtitle: "パートナー技術サポート",
      idLabel: "メインアカウント ID",
      idRequired: "メインアカウント ID を入力してください",
      idPlaceholder: "メインアカウント / テナント ID（例: 1011010000068）",
      submit: "チャットを開始",
      notFound: "アカウントが見つからないか無効化されています",
    },
  },
  ko: {
    emptyTitle: "안녕하세요, Tevau 어시스턴트입니다",
    handoff: "해결되지 않았나요? 상담원과 대화하기 →",
    thinking: "생각 중…",
    send: "보내기",
    buLogin: {
      title: "Tevau AI 지원",
      subtitle: "파트너 기술 지원",
      idLabel: "주 계정 ID",
      idRequired: "주 계정 ID를 입력하세요",
      idPlaceholder: "주 계정 / 테넌트 ID (예: 1011010000068)",
      submit: "채팅 시작",
      notFound: "계정을 찾을 수 없거나 비활성화되었습니다",
    },
  },
  pt: {
    emptyTitle: "Olá, sou o assistente do Tevau",
    handoff: "Não resolvido? Fale com um atendente →",
    thinking: "Pensando…",
    send: "Enviar",
    buLogin: {
      title: "Suporte Tevau AI",
      subtitle: "Suporte técnico para parceiros",
      idLabel: "ID da conta principal",
      idRequired: "Por favor, insira o ID da sua conta principal",
      idPlaceholder: "ID de conta principal / inquilino (ex.: 1011010000068)",
      submit: "Entrar no chat",
      notFound: "Conta não encontrada ou desativada",
    },
  },
  ru: {
    emptyTitle: "Привет, я ассистент Tevau",
    handoff: "Не решено? Связаться с оператором →",
    thinking: "Думаю…",
    send: "Отправить",
    buLogin: {
      title: "Поддержка Tevau AI",
      subtitle: "Техническая поддержка партнёров",
      idLabel: "ID основного аккаунта",
      idRequired: "Введите ID основного аккаунта",
      idPlaceholder: "ID основного аккаунта / арендатора (например, 1011010000068)",
      submit: "Войти в чат",
      notFound: "Аккаунт не найден или отключён",
    },
  },
  th: {
    emptyTitle: "สวัสดี ฉันคือผู้ช่วย Tevau",
    handoff: "ยังไม่ได้รับการแก้ไข? คุยกับเจ้าหน้าที่ →",
    thinking: "กำลังคิด...",
    send: "ส่ง",
    buLogin: {
      title: "ฝ่ายสนับสนุน Tevau AI",
      subtitle: "ฝ่ายสนับสนุนทางเทคนิคของพาร์ทเนอร์",
      idLabel: "รหัสบัญชีหลัก",
      idRequired: "โปรดป้อนรหัสบัญชีหลักของคุณ",
      idPlaceholder: "รหัสบัญชีหลัก / รหัสผู้เช่า (เช่น 1011010000068)",
      submit: "เริ่มแชท",
      notFound: "ไม่พบบัญชีหรือถูกปิดใช้งาน",
    },
  },
  tr: {
    emptyTitle: "Merhaba, ben Tevau asistanıyım",
    handoff: "Çözülmedi mi? Bir temsilciyle konuş →",
    thinking: "Düşünüyorum…",
    send: "Gönder",
    buLogin: {
      title: "Tevau AI Destek",
      subtitle: "Ortak teknik destek",
      idLabel: "Ana hesap kimliği",
      idRequired: "Lütfen ana hesap kimliğinizi girin",
      idPlaceholder: "Ana hesap / kiracı kimliği (örn. 1011010000068)",
      submit: "Sohbete gir",
      notFound: "Hesap bulunamadı veya devre dışı",
    },
  },
  vi: {
    emptyTitle: "Xin chào, tôi là trợ lý Tevau",
    handoff: "Chưa được giải quyết? Trò chuyện với nhân viên →",
    thinking: "Đang suy nghĩ…",
    send: "Gửi",
    buLogin: {
      title: "Hỗ trợ Tevau AI",
      subtitle: "Hỗ trợ kỹ thuật cho đối tác",
      idLabel: "ID tài khoản chính",
      idRequired: "Vui lòng nhập ID tài khoản chính của bạn",
      idPlaceholder: "ID tài khoản chính / khách thuê (ví dụ 1011010000068)",
      submit: "Vào trò chuyện",
      notFound: "Không tìm thấy tài khoản hoặc đã bị vô hiệu hóa",
    },
  },
};
for (const [lng, vals] of Object.entries(extra)) {
  resources[lng as keyof typeof resources] = _criticalKeys(vals) as never;
}

// LanguageSwitcher 渲染用：各语言的"母语"自称。读屏 lang 属性走 i18n.language。
export const LANGUAGE_NATIVE: Record<string, string> = {
  ar: "العربية",
  en: "English",
  es: "Español",
  id: "Bahasa Indonesia",
  ja: "日本語",
  ko: "한국어",
  pt: "Português",
  ru: "Русский",
  th: "ไทย",
  tr: "Türkçe",
  vi: "Tiếng Việt",
  zh: "中文繁體",
};

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    // B 端用户默认 en（用户约定）；C 端 webview 走 bridge 同步永远不会落到 fallback
    fallbackLng: "en",
    supportedLngs: ["ar", "en", "es", "id", "ja", "ko", "pt", "ru", "th", "tr", "vi", "zh"],
    interpolation: { escapeValue: false },
    // 外壳语言不再跟随浏览器/设备（navigator）：C 端 webview 由 APP 经 bridge 决定
    // （syncLanguageFromBridge），B 端浏览器无 bridge/无 ?lng/无缓存时回退 fallbackLng=en。
    detection: { order: ["querystring", "localStorage"], caches: ["localStorage"] },
  });

// a11y：让 <html lang> 跟随当前语言，便于读屏软件用正确语音引擎
function syncHtmlLang(lng: string): void {
  if (typeof document !== "undefined") document.documentElement.lang = lng;
}
syncHtmlLang(i18n.language || "zh");
i18n.on("languageChanged", syncHtmlLang);

// APP 12 种语言 → i18n key 归一化映射。APP _toLanguageTag 把 zh 特化为 "zh-Hant"（兼容旧契约），
// 其他直接是 ISO 639-1 二字母（"en"/"ja"/"pt"/...）。Region 后缀（pt-BR/zh-CN）一律取首段。
const SUPPORTED = ["ar", "en", "es", "id", "ja", "ko", "pt", "ru", "th", "tr", "vi", "zh"] as const;
function _normalizeBridgeLanguage(raw: string): string {
  const primary = raw.trim().toLowerCase().split("-")[0].split("_")[0];
  return (SUPPORTED as readonly string[]).includes(primary) ? primary : "en";
}

/**
 * C 端 webview：外壳语言跟随 APP 当前语言（bridge.getEnv().language，12 种之一）。
 * 归一到 i18n 12 种 supportedLngs。URL 显式 ?lng 优先，不被 APP 覆盖（便于调试/指定）。
 * B 端浏览器无 bridge → getEnv 取不到 language → 不改，沿用 ?lng/localStorage/fallbackLng=en。
 */
export async function syncLanguageFromBridge(): Promise<void> {
  if (typeof location !== "undefined" && new URLSearchParams(location.search).get("lng")) return;
  const { bridge } = await import("../hooks/useAppBridge");
  const raw = (await bridge.getEnv()).language;
  if (!raw) return;
  const lng = _normalizeBridgeLanguage(raw);
  if (i18n.language !== lng) await i18n.changeLanguage(lng);
}

export default i18n;
