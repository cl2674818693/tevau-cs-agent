// 测试环境强制中文：jsdom 的 navigator.language 是 en-US，会让 LanguageDetector 选 en，
// 破坏现有断言中文文案的测试。资源已同步打包，changeLanguage 立即生效。
import "@testing-library/jest-dom/vitest";
import i18n from "../src/i18n";

void i18n.changeLanguage("zh");

// antd v6 的响应式 hook 依赖 window.matchMedia，jsdom 没有此 API；
// 给它一个 no-op stub，避免 useBreakpoint 在测试里抛 TypeError。
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });
}

// antd v6 的 ResizeObserver 依赖也要在 jsdom 下 polyfill。
if (typeof window !== "undefined" && !window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// jsdom 25 的 getComputedStyle 不支持 pseudoElt 参数（antd Table measure
// 滚动条会传），但调用本身不致命，吞掉 NotImplemented warning 即可。
if (typeof window !== "undefined") {
  const _origGCS = window.getComputedStyle;
  window.getComputedStyle = ((elt: Element, _pseudoElt?: string | null) =>
    _origGCS.call(window, elt)) as typeof window.getComputedStyle;
}
