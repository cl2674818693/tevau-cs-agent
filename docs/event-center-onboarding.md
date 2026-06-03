# cs-engine ↔ 事项中心 对接备忘

> cs-engine 内部备忘 + 给事项中心团队的字段映射 cheatsheet。
> 真正的协议规范以事项中心团队下发的 `integration-guide-ticket.md` 为准；
> 本文档只记录 **cs-engine 的实现细节** 和 **字段映射策略**。

最后更新：2026-06-03

---

## 一、当前对接对象（事项中心团队）

| 项目 | 值 |
|------|-----|
| 测试接口 | `http://192.168.2.6:922/api/tasks` |
| 测试 Bearer token | `ticket-token-dev` |
| 测试事项中心 UI | `http://192.168.2.6:822` |
| 团队联系人 | 焦坤 |

---

## 二、cs-engine 出站推送

### 实现位置
- 统一客户端：`server/src/ai_engine/integrations/event_center_client.py` `create_task()`
- 工单创建调用方：`server/src/ai_engine/agent/tools/create_ticket.py`（AI 调 `create_ticket` 工具时）
- SLA 升级调用方：`server/src/ai_engine/persistence/maintenance.py:push_pending_takeover_timeouts`

### 请求格式（按事项中心契约）
```
POST {EVENT_CENTER_URL}
Authorization: Bearer {EVENT_CENTER_TOKEN}
Content-Type: application/json

{
  "event_id": "AI-2026-06-03-abcd12",
  "action_type": "task",
  "source_module": "ticket",
  "event_type": "new_ticket",
  "context": "用户反馈 3DS webhook txnCurrency 为 null...",
  "priority": 3,
  "entities": [
    {"type": "customer", "id": "U43825474"},
    {"type": "card", "id": "CIDV012566325407"}
  ],
  "source_ref": "AI-2026-06-03-abcd12",
  "callback_url": "https://cs-engine.tevau.internal/api/v1/event-center/callback"
}
```

---

## 三、字段映射策略

### 3.1 category → action_type

cs-engine 内部 `category` 分 5 类，事项中心 `action_type` 只有 task/notify。映射：

| cs-engine category | action_type | 说明 |
|---|---|---|
| `bug` | `task` | 需要工程师跟进 |
| `事务` | `task` | 需要运营操作 |
| `人工介入` | `task` | 用户明确要转人工 |
| `CQ` | `task` | 一般咨询但需要人答复 |
| `无信息` | `notify` | AI 收集信息不足，记一笔，无需推动客服 |

### 3.2 severity → priority

cs-engine `p0` 最高，事项中心 `4` 最高，反向数字映射：

| cs-engine severity | priority | 含义 |
|---|---|---|
| `p0` | `4` | 紧急 |
| `p1` | `3` | 高 |
| `p2` | `2` | 普通（事项中心默认值）|
| `p3` | `1` | 低 |

### 3.3 evidence → entities

cs-engine 的 `evidence` 是 AI 任意写的字典；事项中心 `entities` 是结构化数组 `[{type, id, name?}]`。

提取规则（`create_ticket._extract_entities`）：
- subject_id 永远是第一条：C 端 → `{type:customer}`，B 端 → `{type:partner}`
- evidence 里识别这些键映射到 entity（同义词都识别）：
  - `card_id` / `cardId` / `card_number` / `cardNumber` → `{type: card}`
  - `transaction_id` / `txn_id` / `order_id` / `orderId` / `trade_no` / `tradeNo` → `{type: transaction}`
- 未识别字段忽略（不抛错），让 AI evidence 自由扩展

### 3.4 source_ref

填 cs-engine 的 `event_id`（与 PK 同步），方便事项中心运营反向跳回 admin 后台审计页：
`https://cs-engine.tevau.internal/admin/tickets/{event_id}`

### 3.5 callback_url

每次推送都带 cs-engine 自己的回调端点 URL（配置项 `EVENT_CENTER_CALLBACK_URL`），事项中心结案后回调到这里。

---

## 四、cs-engine 入站 callback

### 实现位置
`server/src/ai_engine/api/event_center_callback.py`，端点 `POST /api/v1/event-center/callback`。

### 鉴权
- 不验 HMAC（事项中心契约没要求）；改用 Bearer token
- 期望 header：`Authorization: Bearer {EVENT_CENTER_CALLBACK_TOKEN}`
- 错误码：401（缺 / 错 token）、503（cs-engine 未配 token，防裸奔）

### 处理流程
事项中心 POST 进来的 body：
```json
{
  "task_id": 1,
  "event_id": "AI-2026-06-03-abcd12",
  "source_ref": "AI-2026-06-03-abcd12",
  "event_type": "new_ticket",
  "status": "completed",
  "resolution": "已核查，已通知用户",
  "resolution_type": "manual_correction",
  "handled_by": "客服A",
  "created_at": "2026-06-03T14:30:00Z",
  "resolved_at": "2026-06-03T15:10:00Z",
  "response_seconds": 600,
  "resolve_seconds": 2400
}
```

cs-engine 处理：
1. Bearer token 验签
2. 用 `event_id` 在本地 `tickets` 表找 ticket（找不到返 404）
3. `status="completed"` → 落 `ticket_events` 表 event=`closed`；其他 status 透传不翻译
4. 推 SSE 到用户会话（前端 ticket-events-stream 订阅）
5. `closed` 入解决耗时 metric（优先用事项中心传的 `resolve_seconds`，缺省回退本地算）
6. 返回 `{"ok": true}`

---

## 五、配置项

cs-engine 端（环境变量，对应 `server/src/ai_engine/config.py:34-44`）：

```bash
# 出站
EVENT_CENTER_URL=http://192.168.2.6:922/api/tasks
EVENT_CENTER_TOKEN=ticket-token-dev

# 入站
EVENT_CENTER_CALLBACK_URL=https://cs-engine.tevau.internal/api/v1/event-center/callback
EVENT_CENTER_CALLBACK_TOKEN=<另一个随机 token>
```

**两个 token 应当不同**：出站 / 入站独立，任一泄漏隔离影响面 + 便于单独轮换。

---

## 六、不再做的事（明确废弃）

| 旧路径 | 状态 | 替代方案 |
|---|---|---|
| HMAC-SHA256 `X-Signature` 双 key 轮换 | ❌ 已废弃 | Bearer token |
| `POST /api/v1/tickets/{external_id}/events` (旧 HMAC 入站) | ❌ 已删除 | `POST /api/v1/event-center/callback` |
| cs-engine 推 `closed`/`reopen` 回执到事项中心（用户在 cs-engine 内点已解决/拒认时） | ❌ 已删除 | 不外推；只落本地 `ticket_events` + 本地 metric。事项中心是工单状态真源 |
| `event_center_secret_current` / `_previous` 环境变量 | ❌ 已删除 | `event_center_token` + `event_center_callback_token` |

---

## 七、联调清单

### 出站联调（cs-engine → 事项中心）
1. cs-engine 配 `EVENT_CENTER_URL=http://192.168.2.6:922/api/tasks` + `EVENT_CENTER_TOKEN=ticket-token-dev`
2. 触发建工单（最简单：H5 转人工按钮 → 调 `/api/v1/conversations/{id}/request-human`）
3. 事项中心 UI `http://192.168.2.6:822` 应能看到新事项
4. 验证返回的 `task_id` / `assignee_name` 在 cs-engine 端通过返回 dict 接收（虽然目前 cs-engine 没存）

### 入站联调（事项中心 → cs-engine）
1. cs-engine 配 `EVENT_CENTER_CALLBACK_URL` 指向自己 + `EVENT_CENTER_CALLBACK_TOKEN`
2. 事项中心做一条结案操作 → 应 POST 到 cs-engine callback
3. cs-engine 端验证：
   - `ticket_events` 表新增 `event=closed` 行
   - 该 ticket 对应活跃会话用户端 SSE 收到 `closed` 事件
   - `metrics.ticket_resolution_seconds` 有增量

### 历史数据
**不补推**。本地 15 条 ticket 都是测试期产物，无业务价值。上线后从下一条新 ticket 开始。

---

## 八、维护者

- cs-engine 维护：caril
- 事项中心团队联系人：焦坤
- 字典扩展（新 category / severity / event_type）需双方同步本文档
