// React Router + antd App provider 包装的 render：路由组件的统一入口。
// 不接 react-i18n 显式 provider —— src/i18n 在模块导入时已 init。
import { App as AntdApp, ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

type Options = {
  /** 路由初始路径，默认 "/" */
  initialPath?: string;
  /** 渲染路径模式（含参数），默认 "/" */
  path?: string;
  /** 额外的兄弟路由（如登录页、403 页） */
  extraRoutes?: { path: string; element: ReactElement }[];
};

/** 把单个路由组件挂在 MemoryRouter 内渲染。
 *  initialPath 默认等于 path（避免 path=/staff/x 但入口=/ 导致没匹配到 Route → body 空白）。
 *  含动态参数（:id 等）时必须显式传 initialPath 提供实际值。 */
export function renderWithRouter(element: ReactElement, opts: Options = {}) {
  const { path = "/", extraRoutes = [] } = opts;
  const initialPath = opts.initialPath ?? path;
  return render(
    <ConfigProvider locale={zhCN}>
      <AntdApp>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path={path} element={element} />
            {extraRoutes.map((r) => (
              <Route key={r.path} path={r.path} element={r.element} />
            ))}
          </Routes>
        </MemoryRouter>
      </AntdApp>
    </ConfigProvider>,
  );
}
