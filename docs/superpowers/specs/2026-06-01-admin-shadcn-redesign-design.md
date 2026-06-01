# 管理后台 shadcn-admin 全量重写 设计文档

- 日期：2026-06-01
- 范围：`web/` 下所有 `staff/*` + `admin/*` + `BuLoginRoute` + `SpectateRoute` 的 UI 全量重写为 shadcn-admin 风格
- 后端：零改动
- 前端框架：不升级（React 18 / Vite 5 / TS 5.5 保持）

## 1. 背景

现状 `web/src/components/StaffLayout.tsx`（234 行）是 2026-05-25 一次 "AppShell + 侧边栏" 设计的产物，菜单 23 项平铺、自写紫色样式、移动端底部 5-Tab。已有问题：

- 菜单全部一级平铺，找菜单靠肉眼扫
- 自写组件覆盖面有限（`web/src/components/ui/` 仅 12 个），后续新功能要手写 Sheet / Dropdown / DataTable
- 不支持暗色主题
- 移动端 5-Tab 容不下 23 项管理后台菜单

本次以 [`satnaing/shadcn-admin`](https://github.com/satnaing/shadcn-admin) 模板（GitHub ~19k★，MIT）为参考实现完整 shadcn/ui 后台体系。前序两份相关设计：

- `2026-05-25-staff-admin-appshell-design.md` —— 本次替换其产物
- `2026-05-25-web-light-indigo-redesign-design.md` —— 仅改色，本次换整套 token 体系（与之共存于 ChatRoute）
- `2026-05-29-admin-console-design.md` —— 后台功能补齐方案，与本次无冲突

## 2. 范围

### 2.1 In scope

| 路由 | 数量 | 处理 |
|---|---|---|
| `/admin/*`（含 `performance/:staffId` 详情） | 19 | UI 全量重写 |
| `/staff/*`（含 `conversations/:id` `/logs` `/spectate`、`tickets/:externalId`） | 9 | UI 全量重写 |
| `/staff/login`、`/bu/login` | 2 | UI 顺手换风格（不套 AppShell） |
| 新 `AppShell` | 1 | 替换 `StaffLayout` |

合计 30 条 Route UI 重写 + 1 个外壳替换。顶级菜单入口 23 项（admin 18 + staff 5），明细页（5 条 `:id`/`:externalId` 路由）不在 sidebar 出现。

### 2.2 Out of scope

| 项 | 原因 |
|---|---|
| `/` ChatRoute（C 端 webview） | C 端体验关键，UI 不动 |
| 业务功能增删 | 仅 UI，功能等价 |
| 后端 API | 路径/字段/语义全部保持 |
| URL 路径 | 全部 URL 保留，书签不失效 |
| i18n | `admin/staff` 沿用中文硬编码（见 `web/src/i18n/index.ts:5` 约定） |
| React / Vite / TS 大版本升级 | 回归风险大、与本次重写正交 |

## 3. 关键决策

| 决策点 | 结论 | 备选与理由 |
|---|---|---|
| 模板来源 | satnaing/shadcn-admin | 现栈已是 shadcn 子集（radix+cva+tailwind），迁移最顺；备选 TailAdmin / Tremor 风格不匹配 |
| 改造范围 | 全量重写 admin + staff | 用户决定 |
| ChatRoute | 不动 | C 端 webview |
| 主题 | 亮/暗双主题 + 跟随系统，默认亮 | localStorage 记忆 |
| 主色 | `zinc` neutral + `indigo` primary | 与现 `focus-glow` 的 `#4f46e5` 一脉 |
| i18n | admin/staff 中文硬编码 | 沿用 `i18n/index.ts:5` 注释约定 |
| 依赖 | 允许加 shadcn 标配 deps，不升框架大版本 | 见 §6.3 清单 |
| URL | 全部保留 | 书签不失效 |
| 移动端 5-Tab 底栏 | 砍掉，改 Sheet 抽屉 | 23 项后台菜单平铺底 Tab 不合理 |
| CommandPalette | v1 仅菜单跳转 | 全文搜索 YAGNI |
| 组件库管理 | `pnpm dlx shadcn@latest add <comp>` | 用官方版而非手抄 |
| Logo | `lucide` `Headphones` icon + 文字 | 暂不引图片资源；PM 给图后再换 |

## 4. 架构

### 4.1 外壳替换

```
StaffLayout (旧)                AppShell (新)
─────────────────               ─────────────────
hidden md:flex w-220   →        Sidebar (collapsible w-60/w-14)
顶部 ◉ CS 工作台 文字  →        SidebarHeader (logo + 应用名)
flat 23 项菜单         →        CollapsibleGroup x5
                       新增     Topbar (面包屑 + 搜索 ⌘K + 主题 + 头像菜单)
MobileTopBar           →        Topbar (移动端汉堡按钮触发 Sheet)
MobileTabBar (5-Tab)   →        删除（移动端走 Sheet 抽屉）
退出按钮在侧栏底部      →        移到 Topbar 头像 DropdownMenu
```

### 4.2 Token 双轨共存

- **自有 token**（`brand` / `ink.*` / `surface.*` / `line` + 自定义字号 h0..body5）：保留，**仅 ChatRoute 用**，不删
- **shadcn token**（CSS 变量 `--background` / `--foreground` / `--primary` / `--muted` / `--border` / `--ring` + `.dark` 切换）：新增，**admin/staff/BuLogin/Spectate 用**
- `tailwind.config.ts` 两套 namespace 并列；`globals.css` 增加 `:root {…}` 和 `.dark {…}` 变量定义
- ChatRoute 进入时副作用 `document.documentElement.classList.remove("dark")` 兜底，确保 C 端 webview 永远亮色

### 4.3 路由

- 所有现有 `/admin/*`、`/staff/*`、`/bu/login`、`/staff/login` URL 不变
- `<Route element={<StaffLayout />}>` → `<Route element={<AppShell />}>`
- `SpectateRoute`、`ChatRoute`、`BuLoginRoute`、`StaffLoginRoute` 仍不套外壳
- 新增 **403 占位页**：登录态在但 RBAC 无该菜单权限 → 显示 `403 无权限`，替代当前直接 404 跳 `/` 的行为

## 5. 导航信息架构

5 个分组，可折叠，默认全展开，折叠状态写 `localStorage`。组内全部菜单被 RBAC 隐藏时整组隐藏。

| 分组 | 子菜单 | 备注 |
|---|---|---|
| **工作台** | 会话 · 工单 · KPI · 知识缺口 · 工具审计 | `/staff/*` 五项，每日必开 |
| **运营看板** | 数据大盘 · SLA · 客服绩效 · 成本大盘 · 自定义报表 | 数据导向 |
| **质检与审计** | 会话质检 · 操作审计 | 事后回看 |
| **AI 配置** | Prompt 编辑 · Prompt 灰度 · 知识库 · 工具策略 · 范围拦截 | AI/Prompt/KB 工程 |
| **坐席与权限** | 客服账号 · 客服分组 · 在线状态 · 排班 · 会话路由 · 角色权限 | 人员与路由 |

合计 23 项。RBAC 隐藏规则沿用现 `useDynamicMenu` + `PATH_TO_PERM` 映射（在 `StaffLayout.tsx:80-99`），代码搬到 `AppShell` 不改语义。

## 6. 组件体系

### 6.1 现有 12 个组件处理

| 现有 | 处理 |
|---|---|
| `button` `card` `input` `table` `badge` `alert` | 替换为 shadcn 标准版（变体更全、与 DataTable/Form 集成更顺） |
| `avatar` `field` `page` `pager` `empty-state` `spinner` `filter-tabs` | 保留（项目自有或已是 shadcn 标准） |

### 6.2 新增组件（`pnpm dlx shadcn@latest add`）

- **Shell**：`sidebar` `sheet` `separator` `scroll-area` `breadcrumb` `collapsible`
- **表单**：`form` `select` `combobox`（基于 `command`）`checkbox` `radio-group` `switch` `textarea` `label` `popover` `calendar` `date-picker`
- **反馈**：`sonner` `skeleton` `dialog` `dropdown-menu`
- **数据**：`tabs` `command`

### 6.3 新增运行时依赖

```
@tanstack/react-table
react-hook-form
@hookform/resolvers
zod
sonner
cmdk
recharts
date-fns
react-day-picker
@radix-ui/react-{checkbox,collapsible,dropdown-menu,label,popover,
                  radio-group,scroll-area,select,separator,switch,tabs}
```

## 7. 主题与品牌

- 默认 `light`，首访检测 `prefers-color-scheme`，用户主动切换后写 `localStorage.theme`
- `<ThemeProvider>` 包在 `AppShell` 外，不包 ChatRoute
- 切换控件在 Topbar 右侧（图标 `Sun` / `Moon` / `Monitor`）
- 应用名：**Tevau 客服 AI 引擎**（Sidebar 顶 + 浏览器 title）
- Logo：`lucide-react` `Headphones` icon
- 浏览器 title 按页面动态写：`{页面名} · Tevau 客服 AI 引擎`

## 8. 页面模板规约

| 类型 | 数量 | 结构 |
|---|---|---|
| 列表页 | ~15 | `PageHeader`（标题+描述+右上 actions）→ 工具栏（搜索 + 过滤 Chips + 列设置）→ `DataTable`（排序/分页/列固定/隐藏）→ 行尾 `DropdownMenu`；编辑/新建走 `Sheet` 抽屉 |
| 看板页 | ~4 | 顶部时间范围 → `KpiCard` 横向 4-5 张 → `recharts` 图表 Grid → 明细 `DataTable` |
| 详情页 | ~5 | `Breadcrumb`+返回 → `Tabs` 分基本/日志/关联 → 关键操作走 `Sheet` |
| 流式日志 | ~2 | 顶部筛选 Chips → 时间倒序卡片列表 → 翻页 |
| 工作台 SSE | ~4 | 维持现三栏布局，仅外壳/控件换 shadcn；**SSE 订阅与状态机零改动** |

### 8.1 表单规约

- `react-hook-form` + `zodResolver`
- 字段错误用 shadcn `<Form>` 的 `FormMessage` 行内展示
- 服务端 4xx detail 回填到字段或顶部 Alert
- 提交结果用 `sonner` toast
- Sheet 内固定底部 Cancel/Save 按钮区

## 9. 迁移策略

每 Phase 独立 PR，自包含、可独立部署。

| Phase | 内容 | 风险 |
|---|---|---|
| **0** | 依赖安装、shadcn token 接入、`AppShell` + Sidebar 分组 + Topbar + CommandPalette + 主题切换。**所有现有页面套进新 Shell，内部不动**。可上线。 | 低 |
| **1** | 列表类批量迁移：staff-groups → staff → rbac → shifts → presence → routing → guardrails → tools → reports → knowledge → audit → qa（每 2-3 页一 PR） | 中 |
| **2** | 看板类：dashboard / sla / cost / performance / kpi。统一 KpiCard + recharts。 | 中 |
| **3** | 详情类：conversation logs / ticket detail / staff performance detail / prompt-editor | 中 |
| **4** | 工作台 SSE：conversations / tickets / spectate / insights / audits + ChatWindow 周边外壳。**单 PR 严格 review，不与其他改动混合。** | 高 |
| **5** | 删 `StaffLayout.tsx` + dead code + `tailwind.config` 清理 | 低 |

## 10. 测试与验收

### 10.1 自动化

- 每 PR 必过：`pnpm typecheck && pnpm lint && pnpm test:ci && pnpm build`
- 新组件加快照测 + 关键交互测（Sheet 打开/关闭、Form submit、CommandPalette 跳转、Theme toggle 副作用）
- 现有 vitest 全部保留；断言依赖旧 token 名（`bg-brand` / `text-ink-*`）的按需更新
- 不做 e2e（YAGNI）

### 10.2 手动验收清单（每 PR 附）

1. 涉及页面在桌面（≥1280）+ 移动（<768）两档跑通
2. 亮色 + 暗色双主题切换无穿帮
3. 键盘 Tab 顺序合理，`⌘K` 命令面板能跳转
4. 用 agent / supervisor / admin 三种角色登录，菜单与现版相比无新增/缺失项

### 10.3 ChatRoute 回归

Phase 0 合并后立刻全量回归 ChatRoute（webview 内打开跑一遍），确认 C 端 UI 零变化。

## 11. 风险与缓解

| 风险 | 缓解 |
|---|---|
| ChatRoute 间接受 tailwind config 改动影响 | Phase 0 后跑 ChatRoute 全量手动回归；自有 token namespace 不删 |
| 客服 SSE 流改动导致流断 / 状态错乱 | Phase 4 单 PR 严格 review；ChatWindow 内部状态机不重写 |
| RBAC 分组隐藏：组内全无权 → 组隐藏 | AppShell 实现时显式 `group.items.filter(canAccess).length > 0` |
| 暗色下硬编码颜色穿帮 | 重写禁止 hardcoded color，全部走 `text-foreground` / `text-muted-foreground` / shadcn token |
| `pnpm dlx shadcn` 版本飘移 | Phase 0 锁定 shadcn 版本号写入 README |

## 12. 不做（YAGNI）

- e2e 测试
- CommandPalette 全文搜索
- 多语言（admin/staff 仍中文硬编码）
- 自有 token → shadcn 变量的映射统一
- Logo 资源（暂用 lucide icon）
- React 19 / Vite 6 / TS 5.9 升级

## 13. 成功标准

1. 30 个页面全部跑通，原有数据正常展示，原有操作链路（创建/编辑/删除/查询）行为等价
2. `pnpm typecheck && pnpm lint && pnpm test:ci && pnpm build` 全绿
3. 旧 `StaffLayout.tsx` 删除，无僵尸组件残留
4. 暗色主题切换无对比度灾难，DataTable 1000 行不卡
5. ChatRoute UI 与重写前像素级一致
