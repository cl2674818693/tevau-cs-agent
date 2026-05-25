# 全部界面统一重做 — 设计 spec

日期：2026-05-22
范围：`web/`（React 18 + Vite + TypeScript + Tailwind + 类 shadcn 组件）

## 1. 目标

把整个前端的所有界面，统一到现有品牌设计 token 之上，做**视觉重塑 + 组件化**：

- 沿用现有品牌 token（青柠绿 `#C8F833` + 深青墨 `#042834`，及 `ink/surface/status` 色阶、字号体系 `h0..footnote`、圆角、间距），不另起一套皮肤。
- 补全共享 `ui/` 组件库，所有页面复用同一套组件，消除原生 `<input>/<table>/<button>` 的"裸"实现。
- **不改动任何业务逻辑、数据流、路由、API 调用、hooks**。纯展示层重构。

## 2. 现状盘点

共享层（`web/src/components/ui/`）现仅有 `Button`、`Card`（Header/Content）、`Avatar`，工具 `cn`。

| 区域 | 文件 | 视觉状态 |
|---|---|---|
| C 端聊天 | `routes/ChatRoute` → `components/ChatWindow` + 11 个 chat 组件（MessageBubble/MessageList/InputBox/HandoffButton/TicketCard/TicketStatusBanner/ToolCallChip/AiDraftPanel/AiToolsPanel/TakeoverFooter） | 已较成熟：用了 Card/Button/品牌 token、`focus-glow`、`bg-page-gradient`、`safe-top` |
| 登录页 | `routes/BuLoginRoute`、`routes/staff/StaffLoginRoute` | 半成品：原生 `<input>`，已用品牌色与 logo 块 |
| 客服工作台 | `routes/staff/ConversationsListRoute`、`ConversationDetailRoute`、`SpectateRoute`、`KpiRoute` | 裸：原生 `<table>`、原生按钮、无卡片/状态标签，仅用了 token 类名 |
| 管理后台 | `routes/admin/PromptsRoute` | 裸：原生 input + 文本提示 |

测试：`web/tests/*.test.tsx`（约 12 个）覆盖 chat、staff、admin、spectate、ticketStream 等，重构必须保持其全绿；若改动到测试选中的 DOM/文案，同步更新测试。

## 3. 设计方案

### 3.1 补全共享组件库 `web/src/components/ui/`

基于裸页面实际用到的模式抽取（YAGNI：只建被用到的）：

- `Input` / `Textarea`：统一 `focus-glow` 输入框，替换所有原生 `<input>`。受控 props 透传，`forwardRef`。
- `Table` 原语：`Table / THead / TBody / Tr / Th / Td`，表头分隔、数值列右对齐、行 hover。用于 KPI、会话列表（如以表格呈现）。
- `Badge`：状态标签。变体：`pending`（待人工，warning 色）、`takeover`（人工接管，brand 色）、`success`、`error`、`neutral`。用于会话状态、工单状态、角色标识。
- `PageHeader`：抽掉各工作台页重复的「标题（`text-sh2`）+ 右侧操作链接/按钮」头部。props：`title`、`actions?`、`back?`。
- `PageContainer`：抽掉重复的 `mx-auto max-w-[720px] px-page py-block-lg` 外壳；登录页用窄变体（`max-w-[420px]` 居中）。
- `FilterTabs`：会话列表筛选 chips（human_pending / human_takeover / all），受控 `value/onChange/options`。
- `Field`：label + 控件 slot + 错误位的表单行容器。
- `Alert`：提示条，变体 `error / success / info`，用于"已保存并热加载""加载失败""权限不足"等。
- `Slider`：Prompts 灰度分配用；若实现成本高则降级为样式化数值 `Input`（带 % 后缀），二选一在实现时确定，不影响逻辑。
- `EmptyState`：空列表占位（图标 + 文案）。
- `Spinner`：加载态。
- `Card` 现有补充：视需要加 `CardTitle` / `CardFooter`（仅在被用到时加）。

每个组件单一职责、props 接口清晰、可独立测试。

### 3.2 逐页改造（保留全部逻辑）

每页改造 = 把 JSX 的展示层换成共享组件，hooks/effect/API/状态不动。

- **BuLoginRoute / StaffLoginRoute**：`PageContainer`(窄) + `Card` + `Field`+`Input` + `Button`；保留现有 logo 块与错误文案。
- **ConversationsListRoute**：`PageHeader` + `FilterTabs` + 列表项用 `Card`，状态用 `Badge`，补时间/层次；空态用 `EmptyState`，错误用 `Alert`。
- **ConversationDetailRoute**：消息区复用 C 端 `MessageBubble` 视觉风格；状态/工单用 `Badge`，操作用 `Button`，提示用 `Alert`。
- **SpectateRoute**：与详情同风格的只读旁观态。
- **KpiRoute**：`PageHeader` + `Table` 原语重排（表头、斑马纹、数值右对齐），错误用 `Alert`。
- **PromptsRoute**：`PageHeader` + `Card` + 每个版本一行 `Field`+`Slider`/数值 `Input`，合计校验提示与"已保存"用 `Alert`，`Button` 保存。
- **C 端聊天（ChatWindow + chat 组件）**：保持结构与逻辑，仅做一致性微调（间距/圆角/状态色对齐 token、必要时把内部原生控件换成 `Button`/`Input`），改动幅度最小，优先级最低。

### 3.3 工程约束

- 默认不改 `tailwind.config.ts` 的 token。若某组件确需新 token（如 Badge 的浅底色），在该步骤单独标注并最小化新增。
- 包管理器 pnpm。每页改完执行：`pnpm typecheck` + `pnpm test:ci`；全部完成后 `pnpm build` 确认 dist 可产出。
- Prettier 配置：semi、double-quote、trailingComma=all、printWidth=100、tabWidth=2。改完 `pnpm format` + `pnpm lint`。
- 测试中若 `getByText/getByRole` 命中的结构变化，同步更新对应 `web/tests/*.test.tsx`，不放宽断言、不删测试来"绕过"。

## 4. 拆分与顺序（供实施计划参考）

各页互不耦合，建议顺序：

1. 组件库底座（3.1 全部新增组件 + 各自单测）—— 后续页面的依赖前置。
2. 登录页 ×2（最简单，验证组件库可用）。
3. 会话列表 → 会话详情 → Spectate（工作台主链路）。
4. KPI。
5. Prompts。
6. C 端聊天一致性微调（收尾，最小改动）。

每步独立 typecheck + 测试通过后再进入下一步。

## 5. 非目标（明确排除）

- 不重构布局/导航（不新增侧边栏外壳、不改信息架构）。
- 不改后端、API 契约、路由路径。
- 不引入新依赖的大型 UI 框架；继续用现有 radix + cva + tailwind 栈。
- 不做无关重构（不顺手清理其它代码）。
