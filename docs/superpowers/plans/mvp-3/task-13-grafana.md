# Task 13: Grafana 面板 JSON（4 类视角，spec §12.5 ✅17）

> MVP-3 plan 拆分文件 — 总览见 [README.md](./README.md)。

**Files:**
- Create: `grafana/tevau-ai-engine.dashboard.json`

按 spec §12.5 ✅17 的 4 类视角写 Grafana dashboard JSON：

- [ ] **实时运营** Panel:
  - 在线对话数（`active_conversations`）
  - 当前等待人工的会话数（`human_pending`）
  - AI 平均响应时间（基于 `llm_calls` + `llm_tokens` 推导）
  - 工具调用错误率（`tool_calls{ok="false"} / tool_calls`）

- [ ] **趋势** Panel:
  - 每日对话量（`rate(active_conversations[1d])`）
  - 每日 token 消耗 + 估算成本（自定义查询 `llm_tokens` 折算 $）
  - Top 10 BU/user 用量

- [ ] **质量** Panel:
  - "未解决"比例（`user_resolved_total{event="user_rejected_resolved"} / user_resolved_total`）
  - 工单 SLA 达标率（用 `ticket_resolution_seconds` histogram quantile）
  - 客服平均接管时长（`staff_takeover_duration` quantile）

- [ ] **异常告警** Alert rule:
  - 成本超阈：日 token 总量 > X
  - 错误率高：5min 内 tool error rate > 10%
  - agent 超时多：5min 内 `llm_calls` 超时占比 > 5%
  - 单 BU 短时高频访问：`rate(...) by (bu_id) > Y`

提供导入指引文档（README 加一节）。

- [ ] Commit:
```bash
git add grafana/tevau-ai-engine.dashboard.json README.md
git commit -m "feat(mvp-3): Grafana 面板 JSON（4 类视角：运营/趋势/质量/告警）"
```

---
