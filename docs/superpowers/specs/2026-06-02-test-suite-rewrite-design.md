# 测试套件 v2 全量重写设计

> 日期：2026-06-02
> 状态：已批准（终端 brainstorming 流程）
> 范围：`server/tests/` + `web/tests/`

## 1. 背景

当前测试现状：
- server：377 通过 / 1 失败 / 总覆盖率 82.53%（pytest + pytest-cov）
- web：127 通过 / 4 失败 / 1 跳过（vitest + RTL）
- 测试组织扁平、命名不一致、低覆盖模块明显（`conversation_stream` 59%、`ticket_events_sse` 59%、`staff_subject_info` 60%、`object_store` 49%、`admin_shifts` DAO 48%）
- 异常场景覆盖不均（多数 endpoint 只覆盖 happy path）

目标：以资深测试工程师视角，**全量重写**测试套件，所有 happy path 和异常路径系统化覆盖，让 CI 自动化测试成为可信赖的回归屏障。

## 2. 删除/保留范围

### 删除
- `server/tests/test_*.py`（45 个文件，含两个未提交的新测试）
- `web/tests/*.test.{ts,tsx}`（28 个文件）
- 用 `git rm`，commit 中标记"测试套件 v2 重写第一步"

### 保留
- `server/tests/conftest.py`（夹具基础设施：`fake_stream`、`mysql_url`、`_security_test_env` 等会话级容器）
- `web/tests/setup.ts`（vitest jsdom 引导）

### 回退点
- safety commit `1c94144` 已 push 到 `origin/main`，旧测试随时可 `git checkout 1c94144 -- server/tests web/tests` 取回

## 3. 新目录结构

### server
```
server/tests/
  conftest.py
  unit/                    纯函数 / 业务规则 / pydantic 校验
  persistence/             DAO 层（自有库 + 业务库 via testcontainers）
  api/
    c_side/                C 端用户路由
    bu_side/               B 端座席路由
    admin/                 管理后台路由
  agent/                   runtime + tools + prompts
  e2e/                     跨模块端到端剧本
```

### web
```
web/tests/
  setup.ts
  unit/
    hooks/
    lib/
  components/
    chat/
    staff/
    shell/
  routes/
    c_side/
    staff/
    admin/
  integration/             多 hook+组件剧本
```

## 4. 异常场景标准矩阵

### API（每个 endpoint 至少）
| # | 场景 | HTTP | 说明 |
|---|------|------|------|
| 1 | happy path | 2xx | 标准成功路径 |
| 2 | 未登录 / token 失效 | 401 | 缺 cookie / 过期 token |
| 3 | 越权 | 403 | 跨租户、跨 BU、非该角色 |
| 4 | 参数错误 | 422 | missing / wrong type / 超长 |
| 5 | 资源不存在 | 404 | 错 ID |
| 6 | 状态冲突 | 409 | 工单已关闭 / 已分配 / 重复操作 |
| 7 | 限流 / 配额 | 429 | rate_limit / token_budget |
| 8 | 上游故障 | 502/504 | Anthropic 超时 / 业务库挂 / Redis 挂 |
| 9 | 并发竞态 | - | `asyncio.gather` 触发双写 |
| 10 | 注入 / 越界输入 | - | XSS / SQL keywords / 超长 prompt / redact 命中 |

### 组件（每个 component 至少）
1. 默认渲染 / 空态 / 加载态 / 错误态
2. 用户交互（点击 / 输入 / 键盘快捷键）
3. 边界数据（极长文本 / 空数组 / null 字段 / emoji+中文）
4. SSE 事件驱动场景（验证 `chat-event-driven-no-optimistic` 原则）
5. 权限 / 角色态切换（C/B 端身份差异）

## 5. 技术约定

- **pytest 参数化**：异常矩阵用 `@pytest.mark.parametrize` 表达
- **RTL 查询**：优先 role-based，禁用 `querySelector`
- **网络层 mock**：server 用 `respx`（httpx）、web 用 `vi.fn` mock `fetch`
- **数据库**：
  - 自有库 → SQLite in-memory
  - 业务库（unlimitpay / unlimitcard schema）→ testcontainers MySQL（CI 慢但真实，遵守 `sqlite-vs-postgres-test-gap` 记忆）
- **SSE**：用 `httpx.AsyncClient` + `aiter_lines` 实测流，不 mock SSE 本身
- **覆盖率门槛**：
  - server：`--cov-fail-under=75` → 88
  - web：lines/functions/statements 75 → 85；branches 70 → 80
- **命名**：
  - 文件：`test_{module}_{aspect}.py` / `{Component}.test.tsx`
  - 函数：`test_{verb}_{condition}_{result}`
- **执行时间预算**：
  - server full < 90s（不含 testcontainers）
  - web full < 60s

## 6. 不做的事

- 不删 `conftest.py` 和 `setup.ts`
- 不引入新依赖（pytest-mock / msw / playwright 等）
- 不动 alembic migration 文件（保留 `test_alembic_migrations` 功能但重写）
- 不写"测试的测试"（meta-test）
- 不改业务代码（如果测试发现 bug，列清单不擅自修）
- 不动测试基础设施之外的产品代码

## 7. 执行计划

按 task #1–#14 顺序连续自主推进（用户已批 `feedback_autonomous-plan-execution`）：

1. ✅ safety commit + push（`1c94144`）
2. 📝 本设计 doc（task #1）
3. 🗑 删除现有测试 + 建立新目录（task #2）
4. server unit → persistence → api(c/bu/admin) → agent → e2e（tasks #3-#9）
5. web unit → components → routes → integration（tasks #10-#13）
6. 全量回归 + 覆盖率验证 + 报告（task #14）

每个阶段跑该目录测试，确保 green 再进下一个。最后汇总：通过数、覆盖率、新发现的疑似 bug 清单。
