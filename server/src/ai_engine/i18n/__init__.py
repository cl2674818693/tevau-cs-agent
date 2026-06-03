"""后端 i18n：用户面系统消息/错误提示/greeting/拒答模板按 ui_locale 选语言。

设计原则：
- 只覆盖**直接送到用户**的硬编码字符串（SSE 系统事件、HTTP 错误 body、greeting）。
  AI 经过 LLM 生成的回复走 reply_style prompt 的语言镜像规则，不在此处。
- locale 来源：前端从 APP bridge.getEnv().language 拿到当前 APP 语言，
  通过 `?ui_locale=` query 或请求体字段传给后端。
- 12 种语言对齐 APP（lib/l10n/）：ar/en/es/id/ja/ko/pt/ru/th/tr/vi/zh。
  APP 端 zh 实际下发 "zh-Hant"（兼容旧契约），后端归一为 "zh"。
- 默认值：B 端 BU 工作语言为 en；C 端 webview 走 APP，不会落到默认；浏览器调试无 bridge 时也 en。
"""

from ai_engine.i18n.messages import t, normalize_locale

__all__ = ["t", "normalize_locale"]
