import { App as AntdApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import "dayjs/locale/zh-cn";
import React from "react";
import ReactDOM from "react-dom/client";
import { Toaster as SonnerToaster } from "sonner";

import App from "./App";
import "./i18n";
import { antdTheme } from "./lib/antd-theme";

// AntdApp 注入 message / notification / modal 静态实例的 context，
// 应用内任何位置可通过 `App.useApp()` 拿到，新代码统一走这条。
//
// SonnerToaster 作为 antd 迁移期的过渡兜底：未迁移的路由仍 `import { toast } from "sonner"`，
// 渲染层需要 Toaster 在 DOM 里 toast 才能显示。迁移完所有路由后删除此行 + 卸载 sonner。
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={antdTheme}>
      <AntdApp>
        <App />
        <SonnerToaster richColors closeButton />
      </AntdApp>
    </ConfigProvider>
  </React.StrictMode>,
);
