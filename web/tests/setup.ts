// 测试环境强制中文：jsdom 的 navigator.language 是 en-US，会让 LanguageDetector 选 en，
// 破坏现有断言中文文案的测试。资源已同步打包，changeLanguage 立即生效。
import "@testing-library/jest-dom/vitest";

// 某些沙箱 jsdom 提供的 localStorage / sessionStorage 是空对象，缺 setItem 等方法。
// 用 Map 实现一个最小可用的 Storage，保证 i18n / staffSession 等存储行为可用。
function installStorage(target: typeof globalThis, name: "localStorage" | "sessionStorage") {
  const store = new Map<string, string>();
  const api: Storage = {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(k: string) {
      return store.has(k) ? store.get(k)! : null;
    },
    setItem(k: string, v: string) {
      store.set(k, String(v));
    },
    removeItem(k: string) {
      store.delete(k);
    },
    key(i: number) {
      return Array.from(store.keys())[i] ?? null;
    },
  };
  Object.defineProperty(target, name, {
    configurable: true,
    writable: true,
    value: api,
  });
}

const hasLs =
  typeof (globalThis as unknown as { localStorage?: Storage }).localStorage?.setItem === "function";
if (!hasLs) installStorage(globalThis, "localStorage");
const hasSs =
  typeof (globalThis as unknown as { sessionStorage?: Storage }).sessionStorage?.setItem === "function";
if (!hasSs) installStorage(globalThis, "sessionStorage");

// 必须在 i18n 之前安装 storage（i18n 的 LanguageDetector 会读 localStorage）。
const { default: i18n } = await import("../src/i18n");

void i18n.changeLanguage("zh");

// antd v6 的响应式 hook 依赖 window.matchMedia，jsdom 没有此 API；
// 给它一个 no-op stub，避免 useBreakpoint 在测试里抛 TypeError。
if (typeof window !== "undefined" && !window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      // jsdom 默认当桌面浏览器渲染：(min-width:Xpx) 媒体查询返回 true（"我是桌面"），
      // 让响应式组件默认走 desktop 分支；(max-width:Xpx) 返回 false（"不是 mobile"）。
      // 改前默认 false 等于把所有断点都当 mobile，与桌面端测试预期不符。
      matches: /min-width/i.test(query),
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

// jsdom 不实现 Element.scrollIntoView / scrollTo；ConversationDetailRoute 等
// 组件在 useEffect 里调它做自动滚底，缺失会抛 TypeError 让整测试 crash。
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function () {};
}
if (typeof Element !== "undefined" && !Element.prototype.scrollTo) {
  // @ts-expect-error - Element 类型上没有 scrollTo，但实际运行时 HTMLElement 有
  Element.prototype.scrollTo = function () {};
}

// jsdom 不实现 URL.createObjectURL / revokeObjectURL；AttachButton 预览本地图
// 片时会调，返回一个占位字符串即可（测试不实际渲染 blob 链接）。
if (typeof URL !== "undefined") {
  if (typeof URL.createObjectURL !== "function") {
    URL.createObjectURL = () => "blob:mock";
  }
  if (typeof URL.revokeObjectURL !== "function") {
    URL.revokeObjectURL = () => {};
  }
}
