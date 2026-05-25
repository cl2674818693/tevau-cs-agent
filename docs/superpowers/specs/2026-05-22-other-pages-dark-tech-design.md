# 其他端深色科技感统一 设计 spec

日期：2026-05-22
范围：`web/` 的登录页 / 客服工作台 / 管理后台（C 端聊天已完成，不在本次范围）。延续 C 端深色科技感视觉语言。

## 1. 目标

把其他端统一到深色科技感（深蓝灰底 + 电光青 cyan #22D3EE + 浅色文字），与 C 端协调。

- **手段**：以「全局 token 改深色」为主（改 `tailwind.config.ts` 一处，所有页面 + `ui/` 组件自动跟随），辅以少量组件点缀。
- **深度**：深色底座 + 适度点缀（cyan 主按钮/激活态/聚焦/链接），不逐页堆玻璃光晕。
- **不改业务逻辑/数据流/路由/API**，纯展示层。
- **不用 Stitch**，直接写代码。

## 2. 现状要点（调研结论）

- 8 个路由 + 全部 `ui/` 组件均通过全局语义 token（`brand/ink/surface/line/status`）取色，无硬编码颜色 → 改 config 全局生效。
- C 端聊天用独立 `chat-*` token，**不受全局 token 影响**（不会被破坏）。
- `ui.test.tsx` 断言 class 名：Badge pending 含 `status-warning`、FilterTabs active 含 `bg-brand`、Input placeholder 透传、FilterTabs onChange。→ 保留这些 class 名，仅改 token 值。
- `markdown-body`（浅色）已无引用，死代码，不处理。
- `globals.css` body 当前是浅色 gradient + `#121212` 文字，需改深色。

## 3. Token 方案（重定义全局值，保留所有 token 名）

`tailwind.config.ts` `theme.extend.colors`：

```
brand: { DEFAULT: "#22D3EE", dark: "#0E7490", tab: "#67E8F9", press: "#0891B2", disabled: "#1A232E" }
ink:   { primary: "#F8FAFC", secondary: "#94A3B8", placeholder: "#64748B", subtle: "#94A3B8",
         footnote: "#64748B", onbrand: "#06141B" }   // 新增 onbrand：cyan/brand 底上的深色文字
surface: { page: "#0B0F14", card: "#121A23", subtle: "#161F2A", container: "#1A232E",
           disabled: "#161F2A", hover: "#1F2A37" }
line: "#243140"
status: { error: "#F87171", success: "#4ADE80", warning: "#F59E0B" }   // error/success 提亮以适应深底；warning 保留(=chat accent)
background: "#0B0F14"
foreground: "#F8FAFC"
// shadcn 别名同步：
primary:     { DEFAULT: "#22D3EE", foreground: "#06141B" }
secondary:   { DEFAULT: "#0E7490", foreground: "#F8FAFC" }
muted:       { DEFAULT: "#1A232E", foreground: "#94A3B8" }
accent:      { DEFAULT: "#67E8F9", foreground: "#06141B" }
destructive: { DEFAULT: "#F87171", foreground: "#06141B" }
border: "#243140"
input: "#243140"
ring: "#22D3EE"
card: { DEFAULT: "#121A23", foreground: "#F8FAFC" }
```

`boxShadow.focus` → `0 0 8px 0 rgba(34,211,238,0.25)`（cyan）。
`backgroundImage.page-gradient` → `linear-gradient(180deg, #0B0F14 0%, #0E1620 100%)`。

## 4. globals.css

- body：`background-image` 改深色 gradient（同 page-gradient），`color: #F8FAFC`。
- `.focus-glow:focus-within`：`box-shadow` 与 `border-color` 改 cyan（`rgba(34,211,238,0.25)` / `#22D3EE`）。
- `.markdown-body`（浅色）保留不动（无引用）。`.markdown-body-dark`、`.glass` 等 C 端类不动。

## 5. 组件点缀（少量改动，因 brand→cyan 的文字对比）

- **button.tsx**：`primary` 的 `text-ink-primary` → `text-ink-onbrand`（cyan 底深字）；`active:text-white` 去掉（保持 onbrand）；`secondary`（`bg-brand-dark text-white`）保留；`ghost`/`link` 保留（深底浅字 OK）。
- **filter-tabs.tsx**：active 的 `text-ink-primary` → `text-ink-onbrand`（`bg-brand` class 保留，ui.test 仍通过）。
- **badge.tsx**：`takeover` 的 `text-ink-primary` → `text-ink-onbrand`（`pending` 等保留，含 status-warning class）。
- **avatar.tsx**：fallback 的 `text-ink-primary` → `text-ink-onbrand`。
- 其余 ui 组件（card/input/table/alert/page/field/empty-state）**不改代码**，靠 token 自动深色化。
- Card 不强加玻璃，保持 `bg-surface-card border border-line`（深色实色 + 深边框），点缀靠 cyan 按钮/激活/聚焦体现，保证数据页可读性。

## 6. 对 C 端的影响（可接受）

改全局 `status` 值会让 C 端少数用 `text-status-error/success` 的地方（ErrorView、ToolCallChip B 端）文字更亮——深色下更清晰，与整体一致。C 端其余用 `chat-*`，不受影响。

## 7. 测试锚点（保持全绿）

- `ui.test.tsx`：Badge `status-warning` class、FilterTabs `bg-brand` class、Input placeholder、FilterTabs onChange。
- 其他端测试（staff/spectate/adminPrompts/multiStaff/mvp2 等）：断言文案/交互/role，不涉颜色值。
- 无 toHaveClass 颜色值断言，纯改 token 值安全。

## 8. 工程约束

- 改完 `pnpm typecheck` + `pnpm test:ci` + `pnpm build`；仅对改动文件 `prettier --write` + `eslint`。
- 不改业务逻辑、不动用户其他未提交改动、不全局 format。

## 9. 非目标

- 不改 C 端聊天（已完成）。
- 不重构布局/导航/信息架构。
- 不逐页加玻璃/光晕/网格（保持数据页可读性）。
- 不引入新依赖。
