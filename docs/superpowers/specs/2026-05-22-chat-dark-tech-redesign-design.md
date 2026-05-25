# C 端聊天 — 深色科技感视觉重做 设计 spec

日期：2026-05-22
范围：`web/` 仅 **C 端聊天**（`ChatWindow` + chat 组件）。设计来源：Stitch 项目 `2186759456343743378`（深色科技感，已生成 3 个移动端 screen）。

## 1. 目标

把 C 端聊天界面的视觉从现有浅色品牌，重做为 Stitch 生成的**深色科技感**（深蓝灰底 + 电光青 cyan + 玻璃拟态 + 微光/网格氛围）。

- **纯展示层重构**：不改任何业务逻辑、数据流、hooks、API、路由。
- **保留全部现有文案/交互锚点**：Stitch 设计里的文案是 mock 假数据，落地时**只照搬视觉**，文案/数据/交互沿用现有真实实现（见 §5 测试锚点）。
- **隔离作用域**：深色只作用于 C 端聊天，**不动**工作台/登录/后台的浅色样式与全局 token。

## 2. 设计 token（从 Stitch HTML 精确提取）

| 角色 | 值 |
|---|---|
| primary（cyan） | `#22D3EE` |
| on-primary（深底） | `#0B0F14` |
| surface（页面底） | `#0B0F14` |
| surface-variant（卡片/输入底） | `#1A232E` |
| on-surface（主文字） | `#F8FAFC` |
| on-surface-variant（次文字） | `#94A3B8` |
| accent（人工客服/警告，琥珀） | `#F59E0B` |
| 用户气泡渐变 | `linear-gradient(90deg, #0891B2, #22D3EE)` |
| 状态-成功 | `green-500/400`（已发货等内联标签） |

字体：标题 `Space Grotesk`，正文 `Inter`，标签 `Public Sans`（现有全局是 `Source Sans 3`，仅在聊天作用域内引入新字体）。

效果类（来自 Stitch `<style>`）：
- `.glass`：`background: rgba(11,15,20,0.7); backdrop-filter: blur(16px)`
- `.cyan-glow-border`：`border: 1px solid rgba(34,211,238,0.2); box-shadow: 0 0 15px rgba(34,211,238,0.05)`
- `.amber-glow-border`：`border: 1px solid rgba(245,158,11,0.3)`
- `.grid-bg`：cyan 圆点网格 `radial-gradient(...) 24px`
- `@keyframes breathe`（AI 在线呼吸点）+ `.animate-breathe`

## 3. Token 隔离策略（核心架构决策）

**采用方案：聊天专用色板 + 作用域自定义类，不碰现有全局 token。**

1. `tailwind.config.ts` 的 `extend.colors` 下**新增** `chat` 命名空间（不覆盖现有 `surface/primary/accent`）：
   ```
   chat: {
     primary: "#22D3EE", "on-primary": "#0B0F14",
     surface: "#0B0F14", "surface-variant": "#1A232E",
     "on-surface": "#F8FAFC", "on-surface-variant": "#94A3B8",
     accent: "#F59E0B",
   }
   ```
   聊天组件用 `bg-chat-surface`、`text-chat-primary` 等，与浅色端零冲突。
2. `extend.fontFamily` 新增 `chat-headline: ["Space Grotesk", ...]`、`chat-body: ["Inter", ...]`。
3. `globals.css` 新增 `.glass / .cyan-glow-border / .amber-glow-border / .grid-bg / .animate-breathe / @keyframes breathe`（直接用 rgba 写死，照搬 Stitch），以及深色 markdown 变体 `.markdown-body-dark`（strong/code/pre/blockquote 改为深色配色）。
4. 字体 `@import`：在 `globals.css` 引入 Space Grotesk + Inter（保留现有 Source Sans 3）。

**已知取舍**：此方案下 C 端聊天为深色、其他端（工作台/登录/后台）仍为浅色，全站风格暂不统一。这是「仅 C 端」范围的必然结果；统一其他端为后续独立工作（不在本次范围）。

## 4. 逐组件改造（保留逻辑与文案）

每个组件 = 仅替换 JSX 的 className/结构呈现，props、hooks、事件、条件分支全部不动。

- **ChatWindow**：根容器去掉 `bg-page-gradient`，改 `bg-chat-surface grid-bg text-chat-on-surface font-chat-body`；保留 `max-w-[720px]`、键盘 inset、`safe` 适配。
- **ChatExtras**：
  - `ChatHeader`：深色玻璃 header（`glass border-b border-chat-primary/20`），左侧 logo 块 cyan，标题 `font-chat-headline text-chat-primary`，副行 cyan 呼吸点 + 现有文案（保留「Tevau AI 客服」「由 AI 驱动 · 复杂问题转人工」「客服 X · 已认证」），「停止生成」按钮保留。
  - `StatusBanners`：用 `bg-chat-accent/10 text-chat-accent`，文案不变。
  - `Suggestions`：cyan 描边玻璃 chips，**保留现有 `SUGGESTIONS` 文案**（不是 Stitch 的"查询物流"）。
  - `LoadingView/ErrorView`：深色化，文案不变。
- **MessageBubble**：user→cyan 渐变实底右对齐；assistant→`glass cyan-glow-border` + cyan 发光 AI 头像 + `markdown-body-dark`；human_agent→`glass amber-glow-border` + 琥珀「客」头像 + 「客服 X · 已认证」；system→居中次要文字。`ToolCallChip`/`思考中…` 文案不变。
- **MessageList**：容器间距对齐设计，逻辑不变。
- **ToolCallChip**：C 端 chip 改 cyan 描边小胶囊（图标 + `C_LABELS` 文案，**文案不变**）；B 端可展开版保留（含 `tc.name`、JSON、`getByText(name)` 行为）。
- **TicketCard**：`glass cyan-glow-border` 卡 + 顶部 cyan 渐变光线 + 工单号 + 状态 badge（`statusLabel` 文案不变）；按钮**保留「已解决」「未解决」**且**保留现有 `status==="resolved"` 才显示**的逻辑（不照搬 Stitch 的 in_progress 显示）。
- **TicketStatusBanner**：深色条 `glass` + 文案不变。
- **InputBox**：深色玻璃容器，聚焦 cyan 光晕（替换现有浅色 `focus-glow`，聊天内用 `focus-within:border-chat-primary/50 focus-within:ring-chat-primary/20`），cyan 圆形发送按钮；**保留 placeholder「描述你的问题…」与 `aria-label="发送"`**。
- **HandoffButton**：描边玻璃按钮 + 耳机图标，**保留文案「没解决？转人工 →」**。
- **去掉** Stitch 多生成的底部 tab 导航栏（对话/历史/服务）——原 C 端无此结构。

## 5. 测试锚点（改动必须保持其全绿）

`web/tests/` 中 C 端聊天相关断言依赖以下文案/属性，改造**不得**变更：

- placeholder `描述你的问题…`、`aria-label="发送"`（ChatWindow.test）
- C 端工具 chip `正在查询卡片状态…`，B 端 `query_card`/`query_user` 可点开显示 input（components/identityAndChips.test）
- `search_code`、`结论`、`思考中…`（components.test）
- TicketCard 按钮 `已解决`/`未解决`、状态 `等待受理`（components.test）
- HandoffButton `没解决？转人工 →`（components.test）

无测试断言具体颜色 class，故纯样式替换安全。若某处 DOM 结构调整导致 `getByText/getByRole` 命中变化，同步更新对应测试，不放宽断言、不删测试绕过。

## 6. 工程约束

- 包管理器 pnpm。每改一组组件执行 `pnpm typecheck` + `pnpm test:ci`；全部完成后 `pnpm build`。
- Prettier：semi、double-quote、trailingComma=all、printWidth=100、tabWidth=2。完成 `pnpm format` + `pnpm lint`。
- 默认不改现有全局 token；新增项一律走 `chat-*` 命名 / 作用域类，最小化影响面。

## 7. 非目标

- 不动工作台/登录/后台的样式与全局浅色 token。
- 不改后端、API、路由、hooks、数据流。
- 不引入新 UI 框架；继续用现有 tailwind + lucide 栈（Stitch 用的 Material Symbols 图标改用现有 lucide 等价图标，不新增图标依赖）。
- 不做无关重构。
