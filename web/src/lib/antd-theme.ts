/**
 * antd v6 全局 theme token：
 * - colorPrimary 沿用原 shadcn 主色（indigo 600），保证视觉过渡不突兀
 * - borderRadius / fontSize 取相对克制的值，适配后台密集表单/表格
 * 单一来源，禁止页面里 inline 改 theme，保持视觉一致。
 */
import type { ThemeConfig } from "antd";

export const antdTheme: ThemeConfig = {
  token: {
    colorPrimary: "#4f46e5", // indigo-600，对齐原 shadcn primary
    colorSuccess: "#059669", // emerald-600
    colorWarning: "#d97706", // amber-600
    colorError: "#dc2626",   // red-600
    colorInfo: "#0284c7",    // sky-600
    borderRadius: 8,
    borderRadiusLG: 12,
    fontFamily:
      'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "PingFang SC", "Microsoft YaHei", sans-serif',
    fontSize: 14,
  },
  components: {
    // 表格密度收紧，后台数据多，默认中等会浪费纵向空间
    Table: {
      cellPaddingBlock: 10,
      cellPaddingInline: 12,
      headerBg: "rgba(0, 0, 0, 0.02)",
    },
    Card: {
      paddingLG: 20,
    },
    Layout: {
      headerBg: "#ffffff",
      siderBg: "#fafafa",
    },
  },
};
