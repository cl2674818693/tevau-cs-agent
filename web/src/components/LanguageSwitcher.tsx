import { Select } from "antd";
import { useTranslation } from "react-i18next";

import { LANGUAGE_NATIVE } from "../i18n";

/**
 * B 端浏览器语言切换器（C 端 webview 由 APP bridge 强制同步语言，本组件不展示在 C 端）。
 * 切换后由 i18next 的 localStorage 缓存自动持久化，刷新/进入 chat 页仍保留。
 */
export function LanguageSwitcher({ size = "middle" }: { size?: "small" | "middle" }) {
  const { i18n } = useTranslation();
  const options = Object.entries(LANGUAGE_NATIVE).map(([value, label]) => ({ value, label }));
  const current = i18n.resolvedLanguage ?? i18n.language ?? "en";
  return (
    <Select
      size={size}
      value={current}
      onChange={(v) => {
        void i18n.changeLanguage(v);
      }}
      options={options}
      style={{ minWidth: 120 }}
      aria-label="Language"
    />
  );
}
