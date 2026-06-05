/** F-P1-2: react-markdown 安全配置。
 *
 * react-markdown 默认不解释原生 HTML，但 `[click](javascript:alert(1))` 这种纯 markdown
 * 链接仍会产出带危险协议的 <a>，点一下就 XSS。集中加一层 urlTransform 白名单（只放
 * http/https/mailto/tel + 相对路径 + 锚点），再加 disallowedElements 兜底（防未来不慎
 * 引入 rehype-raw 时危险标签直接放过）。两处 MessageBubble / EventBubble 必须 spread
 * 本 props 而不是手抄 remarkPlugins。
 */
import remarkGfm from "remark-gfm";

const SAFE_URL_PROTOCOLS = /^(https?:|mailto:|tel:)/i;

/** 放行 http/https/mailto/tel/相对路径/锚点；其余（含 javascript:、data:）替换为 #。 */
export function safeMarkdownUrl(url: string): string {
  if (!url) return url;
  // 相对路径或锚点：合法且不引入协议
  if (url.startsWith("#") || url.startsWith("/") || url.startsWith("./")) {
    return url;
  }
  if (SAFE_URL_PROTOCOLS.test(url)) return url;
  return "#";
}

// Note: 不能用 `as const`，会让数组变 readonly 与 react-markdown 的 mutable 类型冲突。
export const safeMarkdownProps = {
  remarkPlugins: [remarkGfm],
  disallowedElements: ["script", "iframe", "object", "embed", "style"],
  urlTransform: safeMarkdownUrl,
};
