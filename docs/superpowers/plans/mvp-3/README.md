# MVP-3 客服工单 AI 引擎 — 实施计划（拆分版索引）

> **本目录是 MVP-3 plan 按 task 拆分后的版本**。每个 task 一个 `.md`。  
> 原合并版（已 deprecated）保留在 `../2026-05-19-MVP-3-客服工单AI引擎.md` 作历史参考。

> **For agentic workers:** 执行某个 task 时，**只读** 该 task 的 `.md` + 本 README + `../../CONTEXT.md`（项目摘要）+ 必要时 spec / MVP-1/MVP-2 已落地代码。

---

## 目标

把 MVP-2 的"AI + 客服 + 用户"系统升级为**完整生产形态**：

- 接入**事项中心真实工单状态机**（替换 mock，启用 HMAC 双 key 轮换）
- 强制**多轮一致性 self-check**（runtime inject）
- 治理**会话长度**与 **API 成本**（token 硬阈值）
- 客服工作台升级为 **C 方案**（AI 辅助 / 草稿审核 / 工具代查 / 多客服协作 / KPI）
- 上线**可观测面板**（阿里云 Prometheus + Grafana 4 类视角）

**Tech Stack**：沿用 MVP-1/2 + 新增 `prometheus_client` + 阿里云 Prometheus 抓取 + Grafana。

**前置**：[MVP-1](../mvp-1/README.md) + [MVP-2](../mvp-2/README.md) plan 已实施完毕。

**关联**：[`../../CONTEXT.md`](../../CONTEXT.md) / [`../../specs/2026-05-18-客服工单AI引擎-design.md`](../../specs/2026-05-18-客服工单AI引擎-design.md)

---

## 阻塞依赖（启动前必须有）

- **事项中心**已立项（2026-05-19 确认 1 周内开工）—— MVP-3 启动前需要：事项中心暴露 `/api/v1/tickets` 接收端点 + 提供 base URL + 共享 HMAC 密钥
- **阿里云 Prometheus 实例** —— 运维提供（公司已用，spec §12.5 ✅17）
- **prompts/ 仓库**或 git 分支机制 —— 用于 Prompt 版本化灰度

---

## Task 清单（按顺序执行）

| # | Task | 关键产出 |
|---|---|---|
| 1 | [事项中心真接 + HMAC 双 key 轮换](task-01-event-center-dual-key.md) | `_CURRENT` / `_PREVIOUS` 验签 + 删除 mock receiver |
| 2 | [self-check 强制 inject](task-02-self-check.md) | `stop_reason=end_turn` 后追加 self-check 一轮 |
| 3 | [会话长度治理](task-03-conv-limits.md) | ≤ 20 轮 / ≤ 100K token + `compact_conversation` 总结+开新 |
| 4 | [单 BU/单 user 日 token 硬阈值](task-04-token-budget.md) | `daily_token_usage` 表 + 80% 提醒 + 100% 拒服 |
| 5 | [客服 ai_draft 草稿审核](task-05-ai-draft.md) | AI 出回复不直发 → 客服 approve / reject+rewrite |
| 6 | [客服旁观模式](task-06-spectate.md) | senior+ 订阅不接管 |
| 7 | [客服调 AI 工具](task-07-staff-ai-tools.md) | staff 端代查接口，结果仅客服可见 |
| 8 | [多客服协作（转工程师 + KPI）](task-08-multi-staff.md) | transfer-to/{role} + KPI 端点 + 看板 |
| 9 | [工单状态 SSE 长连](task-09-ticket-sse.md) | 替换 MVP-2 轮询为实时推送 |
| 10 | [Prompt 版本化 + 哈希分桶灰度](task-10-prompt-versioning.md) ⚠️ 2026-06 已废弃，回归单版本全量 | ~~`prompts/v1.0.0/` 目录 + `registry.yaml` + rollout~~ |
| 11 | [Prompt 管理面板（admin）](task-11-prompt-admin.md) | admin 端点 + 前端可视化调比例 |
| 12 | [Prometheus /metrics + 埋点](task-12-metrics.md) | 关键指标定义 + runtime/tools/tickets/staff 埋点 |
| 13 | [Grafana 面板 JSON](task-13-grafana.md) | 4 类视角 dashboard + alert rules |
| 14 | [E2E MVP-3 验收](task-14-e2e.md) | 7 个剧本（事项中心 / 双 key / self-check / 治理 / 草稿 / 协作 / metrics） |
| 15 | [部署 + 上线 checklist](task-15-deploy.md) | docker-compose + 阿里云 Prometheus 抓取 + 客服账号批量初始化 |

---

## 完成标准

- 所有 pytest / vitest 通过
- 事项中心真接 + HMAC 双 key 轮换工作
- self-check 强制在每轮 `end_turn` 后执行
- 会话长度治理（≤ 20 轮 / ≤ 100K token + 自动总结）生效
- 单 BU/单 user 日 token 硬阈值生效
- 客服工作台 C 方案上线：ai_draft / 旁观 / 工具代查 / 转工程师 / KPI
- 工单状态变化 SSE 长连推前端（替换 MVP-2 轮询）
- ~~Prompt 版本化 + 哈希分桶灰度~~（2026-06 已下线，回归单版本全量）
- Prompt 管理面板可调灰度
- /metrics 暴露所有指标
- Grafana 4 类面板正常显示

---

## MVP-3 完成 = AI 引擎全功能上线

至此 spec 所有 In Scope 功能实施完毕。上线前需要敲定（spec §12.1-§12.2）：

- 数据脱敏字段清单（与后端 + 风控冻结）
- wot / saas 库是否接入
- nexus_test 库只读账号
- 事项中心 base URL + 共享密钥
- 阿里云 Prometheus 抓取配置
- 客服账号批量初始化（前 2 名 APP 客服 + 嘉豪 + 另一对接人 + admin）

---

## 未尽（未来扩展，不在 spec 内）

- 多模态：用户截图上传 → AI 看图诊断（Anthropic Vision）
- 第三方语音入口（电话客服转 AI）
- 跨产品线扩展（除 Tevau API 外的其他产品）
