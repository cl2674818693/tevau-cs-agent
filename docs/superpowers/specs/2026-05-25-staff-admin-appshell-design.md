# 客服后台统一 AppShell（侧边栏导航 + 全后台 UI 收口）设计 spec

日期：2026-05-25
范围：`web/` 的客服工作台 + 管理后台页面（工单列表 / 工单详情 / KPI / Prompt 灰度）。
延续已完成的「深色科技感」视觉语言（全局 token 已深色化、cyan 主色），本次**只做布局/信息架构层**：统一导航 + 各页收口。

## 1. 背景与问题

- 已完成：C 端聊天独立深色改造（`chat-*` token）；其他端「全局 token 深色化 + cyan 底文字」换色（见 git log `全局 token 深色科技感化` / `cyan 底文字改深色`）。
- 那次换色的**非目标**明确写着「不重构布局/导航/信息架构」。结果是：页面换了深色底，但仍是**各自孤立、无统一框架**——例如 Prompt 灰度页 `/admin/prompts` 没有任何导航入口，只能手敲 URL 进入。
- 现状结构：
  - 无路由守卫，各页自己 `if(!token) nav("/staff/login")`。
  - 无共享布局，各页在 `PageHeader` 的 `actions` 里手工塞导航链接（如工单列表的「KPI」）和「退出」按钮。
  - 角色显隐分散（`role==="admin"` 在 Prompts 页内部判断；`canSpectate` 在列表页内部判断）。

## 2. 目标

- 登录后进入带**左侧固定侧边栏**的 AppShell：导航集中、Prompt 灰度有正式入口。
- 守卫与角色显隐**集中到 Layout**，各业务页去掉重复样板。
- 视觉风格：**克制数据感**——深色实色卡片 + cyan 点缀（激活态/聚焦/主按钮），不加玻璃/光晕/网格，保证数据页可读性。
- 不动业务逻辑 / 数据流 / API，纯展示与路由结构层。
- 不引入新依赖、不新增颜色 token（复用 `brand/ink/surface/line/status`）。

## 3. 决策（已与用户对齐）

| 决策点 | 结论 |
|---|---|
| 导航形态 | 左侧固定侧边栏 AppShell |
| 视觉强度 | 克制数据感（深色实色 + cyan 点缀） |
| Spectate 观战页 | **不套侧栏**，保持全屏沉浸；顶部保留「返回工作台」入口 |
| C 端聊天页 `/` | 不在范围内；实现阶段仅**核对**是否受影响（预期不需改，独立 `chat-*` token） |

## 4. 架构

### 4.1 路由结构（`App.tsx` 改为嵌套路由）

```
<Routes>
  /            ChatRoute            ← 不套 shell（C 端聊天，全屏）
  /bu/login    BuLoginRoute         ← 不套 shell
  /staff/login StaffLoginRoute      ← 不套 shell
  /staff/conversations/:id/spectate SpectateRoute  ← 不套 shell（全屏观战）

  <Route element={<StaffLayout/>}>   ← 守卫 + 侧边栏 + <Outlet/>
    /staff/conversations
    /staff/conversations/:id
    /staff/kpi
    /admin/prompts
  </Route>

  *            → Navigate to "/"
</Routes>
```

> 注意 `/staff/conversations/:id/spectate` 须在 `:id` 之前或用更具体匹配，避免被 `:id` 抢路由；用 react-router 时按精确路径分别声明即可。

### 4.2 新增组件 `StaffLayout`（`web/src/components/StaffLayout.tsx`）

职责（单一、可独立测试）：
1. **守卫**：`useStaffSession` 取 token，无 token → `<Navigate to="/staff/login" replace/>`。
2. **布局**：左侧 `<StaffSidebar/>` + 右侧内容滚动区 `<main><Outlet/></main>`。
3. 内容区提供统一外边距与滚动；页面内部仍可用 `PageContainer` 约束表单宽度。

### 4.3 新增组件 `StaffSidebar`（同文件或 `web/src/components/StaffSidebar.tsx`）

- 顶部：产品标识（`◉ CS` 文本/简单 logo）。
- 中部导航（用 `NavLink` 自动激活态）：
  - 工单 → `/staff/conversations`
  - KPI → `/staff/kpi`
  - Prompt 灰度 → `/admin/prompts`，**仅 `role==="admin"` 渲染**
- 底部：当前角色文案 + 「退出」按钮（调用 `useStaffSession().logout` 后跳登录页）。
- 激活态：左侧 cyan 竖条 + cyan 文字（或 `bg-brand/text-ink-onbrand`）；hover 用 `surface-hover`。
- 容器：固定宽约 `220px`，`bg-surface-card` + 右侧 `border-line`，全高。

## 5. 各页面改造（纯展示层）

| 页面 | 改动 |
|---|---|
| `ConversationsListRoute` | 删除 `PageHeader.actions` 里的「KPI」链接与「退出」按钮（移入侧栏）；删除内部 `if(!token) nav` 守卫（Layout 接管）；`role`/`canSpectate` 仍按需用于页面内逻辑 |
| `ConversationDetailRoute` | 去掉重复的返回/退出样板（如有）；守卫交给 Layout |
| `KpiRoute` | 删除「返回工作台」链接与内部守卫（导航走侧栏） |
| `PromptsRoute` | 删除「返回」按钮与内部 `role!=="admin"` 守卫的导航部分（入口已仅 admin 可见）；**保留**「保存」作为页面级操作；保留权限不足时的 `Alert` 兜底（双保险，后端仍为准） |
| `SpectateRoute` | 不套 shell；确认顶部有「返回工作台」入口（无则补） |

`PageHeader` 语义收窄为：标题 + **页面级**操作（如 Prompt「保存」），不再承载全局导航。

## 6. 视觉规范（沿用已定 token）

- 侧栏：`bg-surface-card`，右 `border-line`；激活项 cyan，hover `bg-surface-hover`。
- 内容区背景：沿用 body 的 `page-gradient` 深色。
- 卡片/表格/Badge/Alert：保持现有深色 token，不加玻璃。
- 聚焦：沿用 `focus-glow` 的 cyan 环。
- 不新增颜色、不新增 box-shadow 之外的装饰。

## 7. 测试影响与策略

现有 staff/admin 测试断言文案 / role / 交互。导航搬家会影响**查找位置类**断言：

- 工单列表测试中查找「KPI」链接、「退出」按钮 → 这些移入侧栏。须保证测试渲染时**包含 Layout**（或把断言改为在 Layout+页面组合下查找）。
- Prompts 测试中的「返回」按钮断言 → 移除或改判侧栏入口。
- 守卫从页面移到 Layout → 「未登录跳转」类测试改为针对 `StaffLayout` 验证。

策略：每个受影响测试逐个核对；新增 `StaffLayout` / `StaffSidebar` 的单测（守卫跳转、admin 才显示 Prompt、退出清 token）。改完保持 `pnpm typecheck && pnpm test:ci && pnpm build` 全绿。`ui.test.tsx` 的 class 锚点（`bg-brand`/`status-warning` 等）不受本次影响。

## 8. 工程约束

- 改完 `pnpm typecheck` + `pnpm test:ci` + `pnpm build`；仅对改动文件 `prettier --write` + `eslint --max-warnings=0`。
- 不改业务逻辑、不动用户其他未提交改动、不全局 format、不引新依赖。

## 9. 非目标

- 不改 C 端聊天（仅核对，预期不动）。
- 不改后端 / API / 数据模型。
- 不重定义颜色 token（换色已完成）。
- 不加玻璃/光晕/网格背景（保持数据页可读性）。
- 不做响应式移动端侧栏抽屉（后台桌面优先；如需另立项）。
