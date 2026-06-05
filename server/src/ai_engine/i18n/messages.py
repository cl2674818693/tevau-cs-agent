"""12 语言文案表 + t(key, locale, **kw) 查找函数。

新增文案的步骤：
1. 在 MESSAGES 里加 key + 12 种语言翻译（至少 en 必填，作为兜底）；
2. 用 t("namespace.key", locale, name=...) 调用，按需 format。
"""

from typing import Any

# APP 端 12 种语言对齐 lib/l10n/ supportedLocales：ar/en/es/id/ja/ko/pt/ru/th/tr/vi/zh
# 注意：APP zh 实际下发 "zh-Hant"，normalize_locale 统一归一为 "zh"
SUPPORTED_LOCALES = ("ar", "en", "es", "id", "ja", "ko", "pt", "ru", "th", "tr", "vi", "zh")
DEFAULT_LOCALE = "en"  # B 端 BU 默认英语；C 端 webview 走 APP 同步，不会落此默认


def normalize_locale(raw: str | None) -> str:
    """把 bridge / Accept-Language 来的原始 locale 字符串归一到 SUPPORTED_LOCALES 之一。
    规则：
    - None / 空 / 不识别 → DEFAULT_LOCALE (en)
    - "zh-Hant" / "zh-CN" / "zh-TW" → "zh"
    - "pt-BR" / "pt-PT" → "pt"
    - "en-US" / "en-GB" → "en"
    - 其他 12 种直接命中（大小写不敏感）
    """
    if not raw:
        return DEFAULT_LOCALE
    s = raw.strip().lower()
    # 取首段（zh-Hant → zh，en-US → en）
    primary = s.split("-")[0].split("_")[0]
    if primary in SUPPORTED_LOCALES:
        return primary
    return DEFAULT_LOCALE


# 12 语言文案表。key 用点分命名空间（"error.rate_limited"），value 是 dict[locale, str]。
# str 中支持 Python str.format 占位符（如 "{pct}%"）。
# 缺译时 t() 会按 en → DEFAULT_LOCALE 兜底，避免空字符串。
MESSAGES: dict[str, dict[str, str]] = {
    # ───────────── 错误（SSE error event 文案） ─────────────
    "error.rate_limited": {
        "ar": "الرسائل متكررة جداً، يرجى المحاولة لاحقاً.",
        "en": "Too many messages. Please try again later.",
        "es": "Demasiados mensajes. Por favor, inténtalo más tarde.",
        "id": "Terlalu banyak pesan. Silakan coba lagi nanti.",
        "ja": "メッセージが多すぎます。しばらくしてから再度お試しください。",
        "ko": "메시지가 너무 많습니다. 잠시 후 다시 시도해 주세요.",
        "pt": "Muitas mensagens. Por favor, tente novamente mais tarde.",
        "ru": "Слишком много сообщений. Пожалуйста, повторите попытку позже.",
        "th": "ส่งข้อความบ่อยเกินไป กรุณาลองใหม่ในภายหลัง",
        "tr": "Çok fazla mesaj. Lütfen daha sonra tekrar deneyin.",
        "vi": "Quá nhiều tin nhắn. Vui lòng thử lại sau.",
        "zh": "消息过于频繁，请稍后再试。",
    },
    "error.system_busy": {
        # LLM 并发信号量满载 → 让用户稍后重试，区分于"服务不可用"的 error.internal。
        "ar": "النظام مزدحم، يرجى المحاولة بعد قليل.",
        "en": "System busy, please retry shortly.",
        "es": "Sistema ocupado, por favor inténtalo en breve.",
        "id": "Sistem sibuk, silakan coba lagi sebentar.",
        "ja": "システムが混み合っています、しばらくしてから再度お試しください。",
        "ko": "시스템이 혼잡합니다. 잠시 후 다시 시도해 주세요.",
        "pt": "Sistema ocupado, por favor tente novamente em instantes.",
        "ru": "Система перегружена, пожалуйста, повторите попытку чуть позже.",
        "th": "ระบบหนาแน่น โปรดลองอีกครั้งในไม่ช้า",
        "tr": "Sistem yoğun, lütfen kısa süre sonra tekrar deneyin.",
        "vi": "Hệ thống đang bận, vui lòng thử lại sau giây lát.",
        "zh": "系统繁忙，稍后重试。",
    },
    "error.internal": {
        "ar": "الخدمة غير متاحة مؤقتاً، يرجى المحاولة لاحقاً.",
        "en": "Service temporarily unavailable. Please try again later.",
        "es": "Servicio temporalmente no disponible. Por favor, inténtalo más tarde.",
        "id": "Layanan sementara tidak tersedia. Silakan coba lagi nanti.",
        "ja": "サービスは一時的に利用できません。後ほど再度お試しください。",
        "ko": "서비스를 일시적으로 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        "pt": "Serviço temporariamente indisponível. Por favor, tente novamente mais tarde.",
        "ru": "Сервис временно недоступен. Пожалуйста, повторите попытку позже.",
        "th": "บริการไม่พร้อมใช้งานชั่วคราว กรุณาลองใหม่ในภายหลัง",
        "tr": "Hizmet geçici olarak kullanılamıyor. Lütfen daha sonra tekrar deneyin.",
        "vi": "Dịch vụ tạm thời không khả dụng. Vui lòng thử lại sau.",
        "zh": "服务暂时不可用，请稍后再试。",
    },
    "error.failsoft": {
        "ar": "نعتذر، حدث خطأ مؤقت. يرجى إرسال الرسالة مرة أخرى أو الضغط على \"تواصل مع موظف\".",
        "en": "Sorry, something went wrong on our side. Please resend, or tap \"Talk to a human\".",
        "es": "Lo sentimos, hubo un problema. Por favor, envía de nuevo o toca \"Hablar con un agente\".",
        "id": "Maaf, terjadi masalah. Silakan kirim ulang atau ketuk \"Bicara dengan agen\".",
        "ja": "申し訳ありません、エラーが発生しました。再送信するか、「担当者と話す」をタップしてください。",
        "ko": "죄송합니다, 문제가 발생했습니다. 다시 보내주시거나 \"상담원과 대화\"를 누르세요.",
        "pt": "Desculpe, algo deu errado. Por favor, envie novamente ou toque em \"Falar com um atendente\".",
        "ru": "Извините, произошла ошибка. Пожалуйста, отправьте сообщение еще раз или нажмите «Связаться с оператором».",
        "th": "ขออภัย เกิดข้อผิดพลาด กรุณาส่งใหม่ หรือกด \"คุยกับเจ้าหน้าที่\"",
        "tr": "Üzgünüz, bir sorun oluştu. Lütfen yeniden gönderin veya \"Temsilciyle konuş\" düğmesine dokunun.",
        "vi": "Xin lỗi, đã xảy ra lỗi. Vui lòng gửi lại hoặc nhấn \"Trò chuyện với nhân viên\".",
        "zh": "抱歉，我这边暂时出了点问题，请重发一次，或点'转人工'。",
    },
    # ───────────── 警告（SSE warning event 文案） ─────────────
    "warning.budget_exhausted": {
        "ar": "تم استنفاد رصيد خدمة الذكاء الاصطناعي اليومي. يرجى المحاولة غداً أو الضغط على \"تواصل مع موظف\".",
        "en": "Your daily AI quota is used up. Please try again tomorrow, or tap \"Talk to a human\".",
        "es": "Tu cuota diaria de IA está agotada. Por favor, inténtalo mañana o toca \"Hablar con un agente\".",
        "id": "Kuota AI harian Anda habis. Silakan coba besok, atau ketuk \"Bicara dengan agen\".",
        "ja": "本日の AI サービス利用上限に達しました。明日再度お試しいただくか、「担当者と話す」をタップしてください。",
        "ko": "오늘의 AI 사용 한도를 모두 사용했습니다. 내일 다시 시도하거나 \"상담원과 대화\"를 누르세요.",
        "pt": "Sua cota diária de IA acabou. Por favor, tente amanhã ou toque em \"Falar com um atendente\".",
        "ru": "Дневная квота ИИ исчерпана. Пожалуйста, попробуйте завтра или нажмите «Связаться с оператором».",
        "th": "โควต้า AI วันนี้หมดแล้ว กรุณาลองใหม่พรุ่งนี้ หรือกด \"คุยกับเจ้าหน้าที่\"",
        "tr": "Günlük AI kotanız doldu. Lütfen yarın tekrar deneyin veya \"Temsilciyle konuş\" düğmesine dokunun.",
        "vi": "Hạn mức AI hàng ngày đã hết. Vui lòng thử lại vào ngày mai hoặc nhấn \"Trò chuyện với nhân viên\".",
        "zh": "您今日的 AI 服务额度已用完，请明日再试，或点'转人工'。",
    },
    "warning.budget_80": {
        "ar": "تم استخدام 80٪ من رصيد خدمة الذكاء الاصطناعي اليومي.",
        "en": "You've used 80% of today's AI quota.",
        "es": "Has utilizado el 80% de tu cuota diaria de IA.",
        "id": "Anda telah menggunakan 80% kuota AI hari ini.",
        "ja": "本日の AI サービス利用量が 80% に達しました。",
        "ko": "오늘 AI 사용량이 80%에 도달했습니다.",
        "pt": "Você usou 80% da cota diária de IA.",
        "ru": "Использовано 80% дневной квоты ИИ.",
        "th": "คุณใช้โควต้า AI ไปแล้ว 80% ของวันนี้",
        "tr": "Bugünkü AI kotanızın %80'ini kullandınız.",
        "vi": "Bạn đã sử dụng 80% hạn mức AI hôm nay.",
        "zh": "您今日 AI 服务额度已用 80%。",
    },
    "warning.handoff_message_recorded": {
        # human_pending 状态下用户发的每条消息的 per-message ack：
        # 让用户立刻看到"已记录"，避免消息石沉大海 → 怀疑卡住 → 重复狂发。
        "ar": "تم تسجيل رسالتك في التذكرة، وسيراجعها الموظف فور اتصاله.",
        "en": "Saved to your ticket — the agent will see this when they come online.",
        "es": "Guardado en tu ticket: el agente lo verá cuando se conecte.",
        "id": "Tersimpan ke tiket Anda — agen akan melihatnya saat online.",
        "ja": "メッセージをチケットに記録しました。担当者がオンラインになり次第確認します。",
        "ko": "티켓에 기록되었습니다. 상담원이 접속하면 확인합니다.",
        "pt": "Salvo no seu ticket — o atendente verá assim que estiver online.",
        "ru": "Сохранено в вашей заявке — оператор увидит сообщение, когда подключится.",
        "th": "บันทึกลงในตั๋วของคุณแล้ว เจ้าหน้าที่จะดูเมื่อออนไลน์",
        "tr": "Talebinize kaydedildi — temsilci çevrimiçi olduğunda görecek.",
        "vi": "Đã lưu vào phiếu của bạn — nhân viên sẽ xem khi trực tuyến.",
        "zh": "已记录到工单，客服上线后会一并查看。",
    },
    "warning.draft_review": {
        "ar": "موظف خدمة العملاء يراجع الإجابة...",
        "en": "An agent is reviewing the reply…",
        "es": "Un agente está revisando la respuesta…",
        "id": "Agen sedang meninjau balasan…",
        "ja": "担当者が回答を確認中です…",
        "ko": "상담원이 답변을 검토 중입니다…",
        "pt": "Um atendente está revisando a resposta…",
        "ru": "Оператор проверяет ответ…",
        "th": "เจ้าหน้าที่กำลังตรวจสอบคำตอบ...",
        "tr": "Temsilci yanıtı inceliyor…",
        "vi": "Nhân viên đang xem lại câu trả lời…",
        "zh": "客服正在 review 您的回答…",
    },
    # ───────────── 系统事件（非错非警，比如会话切换） ─────────────
    "system.conversation_compacted": {
        "ar": "المحادثة طويلة جداً، تم بدء محادثة جديدة لك، conversation_id={id}",
        "en": "The conversation is too long. Started a new one for you, conversation_id={id}",
        "es": "La conversación es demasiado larga. Iniciamos una nueva, conversation_id={id}",
        "id": "Percakapan terlalu panjang. Memulai percakapan baru, conversation_id={id}",
        "ja": "会話が長くなったため、新しい会話を開始しました。conversation_id={id}",
        "ko": "대화가 길어 새 대화를 시작했습니다. conversation_id={id}",
        "pt": "A conversa ficou longa. Iniciamos uma nova, conversation_id={id}",
        "ru": "Беседа стала слишком длинной. Начата новая беседа, conversation_id={id}",
        "th": "บทสนทนายาวเกินไป เริ่มบทสนทนาใหม่ให้แล้ว conversation_id={id}",
        "tr": "Sohbet çok uzun. Sizin için yeni bir sohbet başlatıldı, conversation_id={id}",
        "vi": "Hội thoại đã quá dài. Đã bắt đầu hội thoại mới, conversation_id={id}",
        "zh": "会话过长，已为您开启新对话，conversation_id={id}",
    },
    # ───────────── 首屏 greeting（init_conversation 返回） ─────────────
    "greeting.c": {
        "ar": "أسألني عن حسابك، بطاقاتك، سجل المعاملات، أو أي مشكلة تواجهها.",
        "en": "Ask me anything about your account, cards, transactions, or any issue you're facing.",
        "es": "Pregúntame sobre tu cuenta, tarjetas, transacciones o cualquier problema que tengas.",
        "id": "Tanyakan tentang akun, kartu, transaksi, atau masalah apa pun yang Anda hadapi.",
        "ja": "アカウント、カード、取引履歴、その他お困りのことを何でもお気軽にお尋ねください。",
        "ko": "계정, 카드, 거래 내역 또는 사용 중 문제 등 무엇이든 물어보세요.",
        "pt": "Pergunte sobre sua conta, cartões, transações ou qualquer problema que enfrente.",
        "ru": "Спрашивайте о вашем аккаунте, картах, транзакциях или любых проблемах.",
        "th": "ถามได้เลยเกี่ยวกับบัญชี บัตร รายการธุรกรรม หรือปัญหาการใช้งานต่างๆ",
        "tr": "Hesabınız, kartlarınız, işlemleriniz veya yaşadığınız herhangi bir sorun hakkında sorabilirsiniz.",
        "vi": "Hãy hỏi tôi về tài khoản, thẻ, giao dịch hoặc bất kỳ vấn đề nào bạn gặp phải.",
        "zh": "账户、卡片、交易记录，或使用中遇到的问题，都可以直接问我。",
    },
    "greeting.b": {
        "ar": "يمكنني مساعدتك في تكامل Open API، أعمال البطاقات، استكشاف الأخطاء.",
        "en": "I can help with Open API integration, card operations, and troubleshooting.",
        "es": "Puedo ayudarte con la integración de Open API, operaciones con tarjetas y resolución de problemas.",
        "id": "Saya bisa bantu integrasi Open API, operasi kartu, dan pemecahan masalah.",
        "ja": "Open API の接続、カード業務、トラブルシューティングなどをサポートします。",
        "ko": "Open API 연동, 카드 운영, 문제 해결 등을 도와드릴 수 있습니다.",
        "pt": "Posso ajudar com integração do Open API, operações de cartões e resolução de problemas.",
        "ru": "Помогу с интеграцией Open API, операциями с картами и устранением неполадок.",
        "th": "ช่วยเหลือเรื่องการเชื่อมต่อ Open API การดำเนินงานบัตร และการแก้ไขปัญหาได้",
        "tr": "Open API entegrasyonu, kart işlemleri ve sorun giderme konularında yardımcı olabilirim.",
        "vi": "Tôi có thể hỗ trợ tích hợp Open API, các thao tác với thẻ và xử lý sự cố.",
        "zh": "可以帮你解答 Open API 接入、卡片业务、对接联调等问题。",
    },
    "greeting.g": {
        "ar": "حتى بدون تسجيل الدخول يمكنني الإجابة على أسئلة API واستخدام التطبيق؛ لاستعلام الحساب أو البطاقات أو المعاملات يلزم تسجيل الدخول أولاً.",
        "en": "Even without signing in, I can answer general API and app questions; for account, card, or transaction queries, please sign in first.",
        "es": "Sin iniciar sesión puedo responder preguntas generales de API y de la app; para consultas de cuenta, tarjetas o transacciones, primero inicia sesión.",
        "id": "Tanpa login pun, saya bisa menjawab pertanyaan umum tentang API dan aplikasi; untuk akun, kartu, atau transaksi, harap login dulu.",
        "ja": "ログインしていなくても API やアプリの一般的な質問にはお答えできます。アカウント・カード・取引のご照会は事前にログインが必要です。",
        "ko": "로그인하지 않아도 API와 앱의 일반적인 질문에 답할 수 있습니다. 계정, 카드, 거래 조회는 먼저 로그인이 필요합니다.",
        "pt": "Mesmo sem login, posso responder perguntas gerais de API e do app; para consultas de conta, cartão ou transações, faça login primeiro.",
        "ru": "Даже без входа могу ответить на общие вопросы об API и приложении; для запросов по аккаунту, картам или транзакциям сначала войдите.",
        "th": "แม้ไม่ได้เข้าสู่ระบบ ก็ตอบคำถามทั่วไปเกี่ยวกับ API และแอปได้ การสอบถามบัญชี บัตร หรือธุรกรรม กรุณาเข้าสู่ระบบก่อน",
        "tr": "Giriş yapmasanız da API ve uygulamayla ilgili genel sorulara yanıt verebilirim; hesap, kart veya işlem sorguları için önce giriş yapmanız gerekir.",
        "vi": "Ngay cả khi chưa đăng nhập, tôi có thể trả lời các câu hỏi chung về API và ứng dụng; để tra cứu tài khoản, thẻ hoặc giao dịch, vui lòng đăng nhập trước.",
        "zh": "未登录也能解答 API、APP 使用等通用问题；查询账户、卡片或交易记录需先登录。",
    },
    # ───────────── 拒答模板（超范围话题，topic_classifier 用） ─────────────
    "refusal.c": {
        "ar": "أنا مساعد Tevau، يمكنني فقط مساعدتك في أسئلة الحساب أو البطاقة أو Open API. كيف يمكنني مساعدتك؟",
        "en": "I'm Tevau's support assistant. I only handle questions about your Tevau account, cards, or our Open API. What can I help you with?",
        "es": "Soy el asistente de Tevau. Solo puedo ayudarte con preguntas sobre tu cuenta, tarjetas o nuestra Open API. ¿En qué puedo ayudarte?",
        "id": "Saya asisten Tevau. Saya hanya menjawab pertanyaan tentang akun, kartu, atau Open API Tevau. Ada yang bisa saya bantu?",
        "ja": "私は Tevau のサポートアシスタントです。アカウント、カード、Open API に関するご質問のみお答えできます。どのようなご用件でしょうか？",
        "ko": "Tevau 지원 어시스턴트입니다. 계정, 카드, Open API 관련 질문만 답변드릴 수 있습니다. 무엇을 도와드릴까요?",
        "pt": "Sou o assistente do Tevau. Só atendo perguntas sobre sua conta, cartões ou nossa Open API. Como posso ajudar?",
        "ru": "Я ассистент поддержки Tevau. Отвечаю только на вопросы о вашем аккаунте, картах или Open API. Чем могу помочь?",
        "th": "ฉันคือผู้ช่วย Tevau ตอบได้เฉพาะคำถามเกี่ยวกับบัญชี บัตร หรือ Open API ของ Tevau ให้ช่วยอะไรดีคะ/ครับ?",
        "tr": "Ben Tevau destek asistanıyım. Yalnızca Tevau hesabınız, kartlarınız veya Open API hakkındaki soruları yanıtlıyorum. Nasıl yardımcı olabilirim?",
        "vi": "Tôi là trợ lý hỗ trợ Tevau. Tôi chỉ trả lời câu hỏi về tài khoản, thẻ hoặc Open API của Tevau. Tôi có thể giúp gì cho bạn?",
        "zh": "我是 Tevau 助手，只能帮您处理账户、卡片或 Open API 相关问题。请问您需要咨询哪方面？",
    },
    # ───────────── HTTP/API 错误 body ─────────────
    "auth.tenant_invalid": {
        "ar": "الحساب الرئيسي غير موجود أو معطل.",
        "en": "Main account not found or disabled.",
        "es": "Cuenta principal no encontrada o deshabilitada.",
        "id": "Akun utama tidak ditemukan atau dinonaktifkan.",
        "ja": "メインアカウントが存在しないか、停止されています。",
        "ko": "메인 계정이 존재하지 않거나 비활성화되었습니다.",
        "pt": "Conta principal não encontrada ou desativada.",
        "ru": "Основной аккаунт не найден или отключён.",
        "th": "ไม่พบบัญชีหลักหรือถูกระงับการใช้งาน",
        "tr": "Ana hesap bulunamadı veya devre dışı bırakıldı.",
        "vi": "Tài khoản chính không tồn tại hoặc đã bị vô hiệu hóa.",
        "zh": "主账户不存在或已停用。",
    },
    "handoff.guest_blocked": {
        "ar": "يرجى تسجيل الدخول في التطبيق قبل التواصل مع خدمة العملاء.",
        "en": "Please sign in inside the app before requesting a human agent.",
        "es": "Por favor, inicia sesión en la app antes de solicitar un agente humano.",
        "id": "Silakan login di aplikasi sebelum meminta agen manusia.",
        "ja": "担当者への接続をご希望の場合は、アプリにログインしてからご利用ください。",
        "ko": "상담원 연결을 요청하려면 먼저 앱에서 로그인해 주세요.",
        "pt": "Por favor, faça login no app antes de solicitar um atendente humano.",
        "ru": "Пожалуйста, войдите в приложение перед запросом оператора.",
        "th": "กรุณาเข้าสู่ระบบในแอปก่อนติดต่อเจ้าหน้าที่",
        "tr": "Bir temsilciye bağlanmadan önce lütfen uygulamada oturum açın.",
        "vi": "Vui lòng đăng nhập trong ứng dụng trước khi yêu cầu nhân viên hỗ trợ.",
        "zh": "请先在 APP 内登录后再转接人工客服。",
    },
    # ───────────── 工具内部 note / 错误（AI 看到后会按用户语言转述，但提前 i18n 化更稳） ─────────────
    "tool.search_timeout": {
        "en": "Search timed out, please use more specific keywords.",
        "zh": "搜索超时，请用更具体的关键词。",
    },
    "tool.user_unmapped": {
        "en": "Cannot map current user identity ({subject_id}) to a business user ID; please escalate to a human agent for identity verification.",
        "zh": "无法将当前用户身份({subject_id})映射到业务用户ID，请转人工核实身份。",
    },
}


def t(key: str, locale: str | None = None, **kw: Any) -> str:
    """查 key 的文案。locale 不识别时回退 en；key 不存在抛 KeyError 提醒开发者。

    用法：t("error.rate_limited", "ja") → 日语文案；
         t("system.conversation_compacted", "en", id=42) → 带 format 占位符
    """
    if key not in MESSAGES:
        raise KeyError(f"i18n key not registered: {key!r}")
    bundle = MESSAGES[key]
    lng = normalize_locale(locale)
    # 完整覆盖优先；缺译则回退 en；连 en 都缺的，取该 key 的任意一项（防御性）
    template = bundle.get(lng) or bundle.get(DEFAULT_LOCALE) or next(iter(bundle.values()))
    return template.format(**kw) if kw else template
