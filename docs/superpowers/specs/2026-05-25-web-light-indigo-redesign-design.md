# 全站 web 前端重做 — 亮色 + 靛蓝 设计 spec

日期：2026-05-25
范围：`web/`（React 18 + Vite + TypeScript + Tailwind + 类 shadcn 组件）全部界面

## 0. 背景与动因

现有 UI 是从 Stitch「深色科技感」模板整体套用而来（见 `2026-05-22-chat-dark-tech-redesign-design.md`、`2026-05-22-other-pages-dark-tech-design.md`），并通过最近几个 commit（「全局 token 深色科技感化」）把 `tailwind.config.ts` 的全局 token 也换成了深色青（`brand=#22D3EE`、`surface.page=#0B0F14`）。项目原本的品牌色（青柠绿 `#C8F833` + 深青墨 `#042834`，见 `2026-05-22-ui-unified-redesign-design.md`）已从配置中消失。

套模板带来的系统性问题（用户已逐条指出）：空状态大片真空、青色滥用（标题/描边/网格/辉光/按钮同一色）、满屏点阵网格廉价感、对比度多处不达标、圆角体系混乱（8/12/16/full 并存）、字体混用四套（Source Sans 3 / Inter / Space Grotesk / Public Sans）、深色对金融客服信任调性不符。

本次为**整站视觉重塑**，从根上换掉底座，而非继续在模板上打补丁。

## 1. 目标

把整个前端统一到一套新的「亮色 + 靛蓝」设计底座，做视觉重塑 + 组件化：

- **换底座**：`tailwind.config.ts` 全局 token 从深色青整体替换为亮色 + 靛蓝（颜色 / 字体 / 字号 / 圆角 / 间距 / 阴影 / 动效）。
- **删问题源**：去掉网格背景（`.grid-bg`）、辉光描边（`.cyan-glow-border` / `.amber-glow-border` / box-shadow 辉光）、呼吸点动效（`.animate-breathe` / `@keyframes breathe`）、多余字体（仅保留一套）。
- **组件化**：补全共享 `ui/` 组件库，所有页面复用，消除裸 `<input>/<table>/<button>`。
- **纯展示层**：不改任何业务逻辑、数据流、路由、API 调用、hooks。

## 2. 方向决策（已与用户确认）

| 决策 | 结论 |
|---|---|
| 整体方向 | 明亮金融（亮底、深字、单一品牌色、大留白；像 Stripe/Intercom，信任感最强） |
| 品牌强调色 | 靛蓝 `#4F46E5`（偏现代科技金融，Stripe/Linear 系） |
| C 端聊天空状态 | 只放品牌标记 + 一句欢迎语，垂直居中；**不放引导问题气泡** |
| 转人工入口 | 在 AI 回复里**按需出现**的行动卡；**不做**贴输入框的固定大按钮，也不做 header 常驻入口 |
| 员工台 / 后台 | 一并转亮色（工作工具，亮色是行业标准、长时间看更舒服） |

## 3. 设计系统底座（token 规范）

替换 `tailwind.config.ts` 的 `extend.colors`（移除现有深色 `brand/ink/surface/chat/...` 体系，建立下列语义 token）。落地时用 Tailwind 语义类（如 `bg-surface`、`text-ink`、`bg-brand`），不在组件里写死 hex。

### 3.1 颜色

**表面（亮色，分层）**
| 角色 | 值 | 用途 |
|---|---|---|
| `bg-canvas` | `#F7F8FA` | 页面/聊天画布底 |
| `surface` | `#FFFFFF` | 卡片 / AI 气泡 / 输入框 / header |
| `surface-subtle` | `#F1F3F5` | 次级填充 / hover 底 |
| `surface-muted` | `#E9ECF1` | 禁用底 / 分隔块 |

**文字（ink）**
| 角色 | 值 | 用途 |
|---|---|---|
| `ink-strong` | `#0F172A` | 标题 |
| `ink` | `#334155` | 正文 |
| `ink-muted` | `#64748B` | 次要文字 / 副标题 |
| `ink-subtle` | `#94A3B8` | 占位 / footnote |
| `ink-on-brand` | `#FFFFFF` | 品牌底上的文字 |

**描边**
| 角色 | 值 |
|---|---|
| `border` | `#E2E8F0` |
| `border-strong` | `#CBD5E1` |

**品牌靛蓝**
| 角色 | 值 |
|---|---|
| `brand-soft` | `#EEF0FE` |
| `brand` | `#4F46E5` |
| `brand-hover` | `#4338CA` |
| `brand-pressed` | `#3730A3` |

**状态色**（每个含主色 + 浅底）
| 角色 | 主色 | 浅底 |
|---|---|---|
| success | `#16A34A` | `#DCFCE7` |
| warning | `#D97706` | `#FEF3C7` |
| error | `#DC2626` | `#FEE2E2` |
| info | `#4F46E5`（=brand） | `#EEF0FE` |

对比度：所有正文/次要文字落在 `surface`/`bg-canvas` 上须达 WCAG AA（上述灰阶已满足）。占位字 `ink-subtle` 仅用于 placeholder，不承载实义信息。

### 3.2 字体

- **收敛为一套**：英文 `Inter`，中文回退 `PingFang SC` / `Microsoft YaHei` / `system-ui`。
- **删除** Space Grotesk、Public Sans、Source Sans 3 的引入与对应 `font-chat-headline/chat-body/chat-label`。`globals.css` 顶部 `@import` 只保留 Inter。
- 字号体系 `h0..footnote`（现有 `fontSize` scale）**保留**，仅确认在亮色下的字重/行高观感。层级靠字号 + 字重 + 颜色三者，不靠字体族区分。

### 3.3 圆角（统一）

替换现有 `8/12/16/full` 乱用：
| token | 值 | 用途 |
|---|---|---|
| `rounded-sm` | `8px` | 小元素 / Badge 内 |
| `rounded` (DEFAULT) | `10px` | 按钮 / 输入 |
| `rounded-md` | `12px` | 卡片 / 工单卡 |
| `rounded-lg` | `14px` | 消息气泡 |
| `rounded-xl` | `16px` | 大容器 |
| 头像 | `10px`（方角圆，统一不用圆形） | |
| pill | `full` | 仅 Badge/筛选 chip |

气泡「尖角」：用户气泡右上角、AI 气泡左上角收为 `5px`，形成对话指向。

### 3.4 阴影（亮色，无辉光）

删除所有 cyan/amber 辉光 box-shadow。新增：
| token | 值 |
|---|---|
| `shadow-sm` | `0 1px 2px rgba(15,23,42,.05)` |
| `shadow-md` | `0 4px 12px rgba(15,23,42,.08)` |
| `shadow-lg` | `0 8px 24px rgba(15,23,42,.10)` |

聚焦态：`focus` 用 `0 0 0 3px rgba(79,70,229,.18)` + `border-color: brand`（替换现有 cyan `focus-glow`）。

### 3.5 间距 / 动效

- 间距沿用现有自定义（`page=16px` 等）并贯彻 4/8/12/16/24/32 节奏，不再混入裸 `py-3` 等随意值。
- 动效：过渡 150–250ms ease-out；移除 `breathe` 呼吸动效；在线状态点改为静态绿点（`success` 色），不发光不缩放。装饰性元素加 `aria-hidden`。

## 4. 应用①：C 端聊天（本次完整落地）

只替换展示层，props/hooks/事件/条件分支全部不动。

### 4.1 ChatWindow
- 根容器：`bg-canvas text-ink`，去掉 `grid-bg` / `bg-page-gradient`。保留 `max-w-[720px]`、键盘 inset、`safe` 适配。
- 已在前序改动中移除的底部「建议气泡 + 转人工大按钮」块，**不恢复**。

### 4.2 空状态（核心）
- 当 `messages.length <= 1`（仅欢迎语）时，渲染**垂直居中**的空状态：品牌标记块（靛蓝方角 + "T"）+ 欢迎标题「你好，我是 Tevau 助手」+ 现有欢迎文案（次要色）。
- **不放**任何引导问题 chips（`Suggestions` 组件停用/删除）。
- 有真实消息后，恢复正常聊天流（消息从上往下）。

### 4.3 ChatHeader
- 亮色：`surface` 底 + `border` 下分隔线（不发光）。
- 左：靛蓝方角品牌标记 + 标题「Tevau 客服」(`ink-strong`)。
- 副行：静态绿点 + 「在线 · 智能助手」(`ink-muted`)；human_takeover 态显示「客服 X · 已认证」。
- 副标题去掉「由 AI 驱动 · 复杂问题转人工」这类实现口吻文案。
- 「停止生成」按钮保留（生成中显示）。

### 4.4 消息气泡（MessageBubble）
- user：`bg-brand` 实底 + `ink-on-brand` 文字，右对齐，右上尖角。
- assistant(AI)：`surface` 白底 + `border` + `shadow-sm`，左对齐，左上尖角，靛蓝方角头像「T」，正文用 `markdown` 亮色变体。
- human_agent：用 warning 浅底 `#FEF3C7` + warning 描边 + 「客」头像（warning 色）+「客服 X · 已认证」，与 AI 区分。
- system：居中 `ink-muted` 次要文字。
- `ToolCallChip` / 「思考中…」文案不变，chip 改靛蓝描边浅底小胶囊。

### 4.5 转人工（按需）
- 转人工**不是**常驻 UI。当 AI 判断需要转接 / 用户表达不满触发 handoff 流程时，在 AI 回复下方渲染一张 `brand-soft` 浅靛蓝行动卡：说明文案 + 「转接人工客服 →」按钮（点击调现有 `requestHandoff`）。
- `HandoffButton` 组件可改造为此「行动卡」形态，或新建轻组件；保留其 `onClick=requestHandoff` 行为与无障碍标签。文案保留「转人工」语义（测试锚点见 §7）。

### 4.6 工单卡 / 状态条 / 输入框
- TicketCard：`surface` 白底 + `border` + `shadow-sm` + 工单号 + 状态 Badge（`statusLabel` 文案不变）；保留「已解决」「未解决」按钮及 `status==="resolved"` 才显示的逻辑。
- TicketStatusBanner：亮色条，文案不变。
- StatusBanners：用 warning/info 浅底，文案不变。
- InputBox：`surface` 白底 + `border` 容器，聚焦 §3.4 靛蓝焦点环；靛蓝方角发送按钮（无辉光，禁用态变灰）；保留 placeholder「描述你的问题…」、`aria-label="发送"`、自动撑高、Enter 发送/Shift+Enter 换行逻辑。

## 5. 应用②：员工台（后续独立 spec→计划）

复用同一底座。先在底座层补全共享组件，再逐页改造（仅展示层）。

**共享 `ui/` 组件**：`Button`(主/次/幽灵/危险)、`Input`/`Textarea`、`Card`(Header/Content/Footer)、`Badge`(pending=warning / takeover=brand / success / error / neutral)、`Table`(THead/TBody/Tr/Th/Td；表头分隔、数值右对齐、行 hover、斑马纹)、`PageHeader`(title + actions + back?)、`PageContainer`(居中宽度壳，登录用窄变体)、`FilterTabs`、`Field`(label+控件+错误位)、`Alert`(info/success/error)、`EmptyState`、`Spinner`。每个单一职责、props 清晰、可独立测试。

**逐页**：
- BuLoginRoute / StaffLoginRoute：窄 PageContainer + Card + Field/Input + Button；保留 logo 与错误文案。
- ConversationsListRoute：PageHeader + FilterTabs + 列表卡 + 状态 Badge；空态 EmptyState，错误 Alert。
- ConversationDetailRoute：消息区复用 C 端气泡风格；状态/工单 Badge，操作 Button，提示 Alert。
- SpectateRoute：与详情同风格的只读旁观态。
- KpiRoute：PageHeader + Table（表头/斑马纹/数值右对齐）。

## 6. 应用③：管理后台（后续独立 spec→计划）

- PromptsRoute：PageHeader + Card + 每版本一行 Field + Slider/数值 Input（Slider 实现成本高则降级为带 % 后缀的数值 Input）；合计校验与「已保存」用 Alert，Button 保存。

## 7. 测试锚点（改动须保持全绿）

`web/tests/*.test.tsx`（约 12 个）依赖下列文案/属性，纯样式替换不得变更；若 DOM 结构调整导致 `getByText/getByRole` 命中变化，**同步更新对应测试，不放宽断言、不删测试绕过**：
- placeholder `描述你的问题…`、`aria-label="发送"`
- C 端工具 chip `正在查询卡片状态…`；B 端 `query_card`/`query_user` 可展开显示 input
- `search_code`、`结论`、`思考中…`
- TicketCard 按钮 `已解决`/`未解决`、状态 `等待受理`
- 转人工文案锚点（现 `没解决？转人工 →`）：若改为行动卡形态导致文案变化，同步更新 `components.test`。
- 登录/会话列表/KPI/Prompts/旁观 相关断言：逐页改造时核对。

## 8. 工程约束

- 包管理器 pnpm。每改一组组件/每页执行 `pnpm typecheck` + `pnpm test:ci`；全部完成后 `pnpm build` 确认 dist 可产出。
- Prettier：semi、double-quote、trailingComma=all、printWidth=100、tabWidth=2。完成 `pnpm format` + `pnpm lint`。
- **本次明确要改 `tailwind.config.ts` 全局 token**（换底座是目标本身），同时清理 `globals.css` 里的深色科技感残留（grid/glow/breathe/多字体 import/深色 markdown 变体改为亮色）。

## 9. 拆分与顺序（供实施计划参考）

1. **设计系统底座**：换 `tailwind.config.ts` token + 清理 `globals.css` + 建全部共享 `ui/` 组件（各自单测）。后续所有页面的依赖前置。
2. **应用①：C 端聊天**（本 spec 主体，最高优先级）。
3. 应用②：员工台（登录 → 会话列表 → 会话详情 → 旁观 → KPI）——独立 spec→计划。
4. 应用③：管理后台 Prompts——独立 spec→计划。

每步独立 typecheck + 测试通过后再进入下一步。

## 10. 非目标

- 不改后端、API 契约、路由路径、hooks、数据流。
- 不重构信息架构（不新增侧边栏外壳等，除非后续单独提）。
- 不引入新的大型 UI 框架；继续用现有 tailwind + radix + cva + lucide 栈。
- 不做无关重构（不顺手清理其它代码）。
