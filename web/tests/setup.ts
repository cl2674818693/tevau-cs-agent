// 测试环境强制中文：jsdom 的 navigator.language 是 en-US，会让 LanguageDetector 选 en，
// 破坏现有断言中文文案的测试。资源已同步打包，changeLanguage 立即生效。
import "@testing-library/jest-dom/vitest";
import i18n from "../src/i18n";

void i18n.changeLanguage("zh");
