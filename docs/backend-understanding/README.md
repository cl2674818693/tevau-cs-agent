# Tevau 后端理解 —— 客服 AI 引擎对接资料

> 为「客服工单 AI 引擎」对接 Tevau 后端而通读三个后端服务产出的资料。
> 源码仓库：`/Users/sunchenglin/codes/后端代码/{TevauNexus-Service, TevauPay-Service, TevauPayAdmin-Service}`、APP 前端 `/Users/sunchenglin/codes/tevau-pay-flutter`。

## 文档导航

| 文档 | 内容 |
|---|---|
| [identity-and-auth.md](identity-and-auth.md) | **身份与鉴权机制**（C 端 Sa-Token / B 端 apiKey+tenant_id）+ 对我方系统的对接结论。**最关键，先读这份**。 |
| [TevauPay-Service.md](TevauPay-Service.md) | C 端 APP 后端接口地图（262 controller / ~320 接口） |
| [TevauNexus-Service.md](TevauNexus-Service.md) | B 端 OpenAPI 后端接口地图（73 controller / ~190 接口） |
| [TevauPayAdmin-Service.md](TevauPayAdmin-Service.md) | 管理后台接口地图（152 controller / ~290 接口，22 业务域） |
| `raw/` | grep 提取的原始清单（mappings / rich / controllers / authfiles），文档据此整理 |

合计 **487 controller / ~800 接口**。

## 系统全景

```
C 端持卡用户 ──APP(tevau-pay-flutter, Flutter)──→ TevauPay-Service ──┐
                                                                      ├─→ 业务库 unlimitpay_test（按 user_id）
B 端企业合作伙伴 ──OpenAPI(apiKey+签名)──→ TevauNexus-Service ────────┤
                                                                      └─→ 业务库 tevau_nexus_test（按 tenant_id）
内部运营/客服/风控/财务 ──→ TevauPayAdmin-Service（Shiro+OAuth2 RBAC）

客服 AI 引擎（本项目）：C 端 webview 内嵌 h5 / B 端浏览器 → 识别身份 → 受限只读查上面两个业务库 → 答疑/建工单
```

## 身份对接速查（详见 identity-and-auth.md）

- **C 端**：APP(Sa-Token) 登录 → 经 js_bridge 把 token 给 h5 → 我方带 `Authorization` 调 `POST /user/getCurrentUserInfo` 拿 `userCode` → 查 `t_tevaupay_user.user_code` 得 `id`(=user_id) → 按 user_id 查 unlimitpay 库。**`auth/c_jwt.py` 的 RS256 方案作废**。
- **B 端**：每家对接公司有「主账户ID」= `tenant_id`（网关由 apiKey 解析）→ 我方 B 端 subject_id 用 tenant_id → 按 tenant_id 查 nexus 库。

## 对客服 AI 系统最有价值的接口/能力

- **C 端查数据**（TevauPay）：卡状态/冻结原因（`getFreezeHistory`）、KYC 实名、余额、交易/转账结果（`getTxResult`）、失败率（`transSuccessRate`）。
- **B 端查数据**（TevauNexus）：订单/账单（`NexusBillingHistoryController`）、余额/卡信息（`QueryController`）、订单/卡交易流水。BU 的 OpenAPI 请求日志网关层记录、无现成查询接口 → 直接查表 `t_nexus_third_request_log`。
- **管理后台**（TevauPayAdmin）：大量现成客服处置能力（解锁卡/重置PIN/改状态、退款/调账、KYC审核、充提币风控审核、对账报表）。无独立"客服工单" controller。建议 AI 只读查询直接复用、写动作走受控确认。

## 已知待办（对接时确认）
- `getCurrentUserInfo` 返回 JSON 的用户主键字段名（VO 只有 userCode，需 userCode→id 这一跳）。
- C 端身份换取需 TevauPay-Service 测试环境地址（本地未起 Java 服务，"token 换 userId"端到端待接）。
- BU「主账户ID」与库内 `tenant_id` 取值是否完全一致（探查见 [business-db](../../) / RDS）。
