import { App as AntdApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import "dayjs/locale/zh-cn";
import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./i18n";
import { antdTheme } from "./lib/antd-theme";

// AntdApp 注入 message / notification / modal 静态实例的 context，
// 应用内任何位置可通过 `App.useApp()` 拿到。
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={antdTheme}>
      <AntdApp>
        <App />
      </AntdApp>
    </ConfigProvider>
  </React.StrictMode>,
);
