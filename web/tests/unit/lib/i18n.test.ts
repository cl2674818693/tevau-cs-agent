// i18n 模块行为：
// - 默认资源 zh/en 完备
// - changeLanguage 同步 <html lang>
// - syncLanguageFromBridge：APP 语言归一到 zh/en；显式 ?lng 不覆盖
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const getEnvMock = vi.fn<() => Promise<{ language?: string }>>();
vi.mock("@/hooks/useAppBridge", () => ({
  bridge: { getEnv: () => getEnvMock() },
}));

import i18n, { syncLanguageFromBridge } from "@/i18n";

describe("i18n", () => {
  beforeEach(() => {
    getEnvMock.mockReset();
    // setup.ts 已强制 zh，每个测试可能改 lng，afterEach 复位。
  });
  afterEach(async () => {
    await i18n.changeLanguage("zh");
    // 清掉 URLSearchParams 影响
    window.history.replaceState({}, "", "/");
  });

  it("zh/en 资源完整覆盖核心 key", () => {
    for (const lng of ["zh", "en"]) {
      const t = i18n.getFixedT(lng);
      expect(t("chat.thinking")).toBeTruthy();
      expect(t("chat.send")).toBeTruthy();
      expect(t("header.title")).toBeTruthy();
      expect(t("ticket.resolved")).toBeTruthy();
      expect(t("error.title")).toBeTruthy();
    }
  });

  it("中文：插值变量回填", () => {
    expect(i18n.getFixedT("zh")("chat.quota", { pct: 90 })).toContain("90");
  });

  it("changeLanguage 把 <html lang> 同步成新语言", async () => {
    await i18n.changeLanguage("en");
    expect(document.documentElement.lang).toBe("en");
    await i18n.changeLanguage("zh");
    expect(document.documentElement.lang).toBe("zh");
  });

  describe("syncLanguageFromBridge", () => {
    it("APP language='en' → 切到 en", async () => {
      getEnvMock.mockResolvedValue({ language: "en" });
      await syncLanguageFromBridge();
      expect(i18n.language).toBe("en");
    });

    it("APP language='zh-Hant' 归一为 zh", async () => {
      getEnvMock.mockResolvedValue({ language: "zh-Hant" });
      await syncLanguageFromBridge();
      expect(i18n.language).toBe("zh");
    });

    it("APP language 缺省时不改", async () => {
      await i18n.changeLanguage("en");
      getEnvMock.mockResolvedValue({});
      await syncLanguageFromBridge();
      expect(i18n.language).toBe("en");
    });

    it("URL 显式 ?lng 时跳过 bridge 同步", async () => {
      window.history.replaceState({}, "", "/?lng=en");
      await i18n.changeLanguage("zh");
      getEnvMock.mockResolvedValue({ language: "en" }); // 即便 bridge 想切
      await syncLanguageFromBridge();
      expect(i18n.language).toBe("zh"); // 未变
      expect(getEnvMock).not.toHaveBeenCalled();
    });
  });
});
