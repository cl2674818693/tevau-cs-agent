# TevauNexus-Service 接口地图（B 端 OpenAPI 后端）

> 本文档由 `docs/backend-understanding/raw/nexus-*.txt`（grep 提取的控制器声明 / 路径注解 / @ApiOperation 描述 / 方法签名）整理而成。
> 功能描述优先使用源码 @ApiOperation 中文原文；提取数据中没有描述的标注 **(无描述)**。

---

## 1. 服务概述

TevauNexus-Service 是 Tevau 的 **B 端 OpenAPI 后端**（项目根目录 `TevauNexus-Service`）。它把 Tevau APP（C 端）的能力（开卡、充值、销卡、冻结、KYC、查询余额账单、交易回调等）包装成一套开放接口，提供给**企业合作伙伴 BU**（对接公司）调用。

- **多租户模型**：按 `tenant_id` 区分对接公司。每个企业合作伙伴对应一个 tenant，所有 OpenAPI 调用都在 tenant 维度做数据隔离与计费。
- **微服务拆分**：服务按业务域拆成多个 Maven 模块（gateway / user / card / trade / query / account / settlement / datacenter / webhook / upms / mq-consumer / job）。每个模块内部又分 `-api`（对外 OpenAPI）、`-server`（内部实现 + feign RPC）、`-common`（feign 客户端声明 / DTO）等子工程。
- **接口分层（重要，看路径前缀就能区分）**：
  - `/openapi/**`：**对外 OpenAPI**，企业合作伙伴 BU 通过网关调用，走 apiKey + 签名鉴权。
  - `/openadmin/**`：**运营后台（B 端管理台 / 企业后台）** 接口，走后台账号登录态（Shiro/Oauth2 token + 可选谷歌验证码）。
  - `/feign/**`、`/account`、`/tenant/account`、`/tevau/account`、`/trade/**`、`/settlement`、`/refund/**`、`/web/hook`、`/nexus/webhook/api` 等：**服务间内部 RPC（Feign）** 接口，不直接对企业开放（webhook 的 openapi 子集除外）。
  - `/upms/**`、`/sys/**`：运营后台的管理功能（客户管理、仓储发卡、KYC 审核、字典、角色权限、日志等）。

### 鉴权机制（已知 + authfiles 佐证）

对外 OpenAPI 的鉴权在**网关层**（`tevau-nexus-gateway`）完成：

- 企业合作伙伴持有 **apiKey + secret**（区分沙箱/生产，见 `TNexusCompanyConfigController` 的 `keyValue/{type}`，type=1 沙箱、type=2 生产）。
- 请求带 **签名（signature）**，网关 `ApiSecurityUtils` / `ApiAuthConfig` 校验签名、`EncryptRequestParamsFilter` 做参数加解密、`RateLimitService` 做限流、`RequestModifyFilter` / `ResponseModifyFilter` 改写请求响应。
- 网关校验通过后**解析出 tenant_id**，通过 `TenantContextHolderFilter` / `BaseFeignTenantInterceptor` 透传到下游各微服务，下游据此做租户隔离。
- 运营后台（`/openadmin`、`/sys`）走另一套鉴权：Shiro + Oauth2（`Oauth2Filter` / `Oauth2Realm` / `TokenGenerator`），密码用 BCrypt，登录可叠加**谷歌验证码（GoogleAuthenticator / TOTP）**。
- 企业 IP 白名单（`TNexusCompanyIpController`）也是访问控制的一部分。

---

## 2. 按模块分组的接口清单

> 说明：`-common` 里的 `XxxFeign.java` 是 Feign **客户端声明**，与对应 `-server` 控制器的接口一一对应（同路径同方法）。下文以**实际暴露接口的控制器**为主列出；Feign 声明仅在能补充中文描述时引用，不重复计为独立接口。

---

### 2.1 模块：tevau-nexus-card（卡服务）

#### ApiCardController（对外 OpenAPI 卡操作）
类级前缀：`/openapi/card`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openapi/card/submitCard/v1 | 提交开卡 (无描述，方法名 submitCard) |
| POST | /openapi/card/rechargeCard/v1 | 卡充值 (无描述，方法名 rechargeCard) |
| POST | /openapi/card/destroyCard/v1 | 销卡 (无描述，方法名 destroyCard) |
| POST | /openapi/card/freezeCard/v1 | 冻结卡 (无描述，方法名 freezeCard) |
| POST | /openapi/card/unFreezeCard/v1 | 解冻卡 (无描述，方法名 unFreezeCard) |
| POST | /openapi/card/lockCard/v1 | 锁卡 (无描述，方法名 lockCard) |
| POST | /openapi/card/unLockCard/v1 | 解锁卡 (无描述，方法名 unLockCard) |
| POST | /openapi/card/getCardPanHtml/v1 | 获取卡 PAN HTML (无描述，方法名 getCardPanHtml) |
| POST | /openapi/card/respondTo3DSVerification/v1 | 3DS 验证响应 (无描述，方法名 respondTo3DSVerification) |
| POST | /openapi/card/updatePhone/v1 | 更新手机号 (无描述，方法名 updatePhone) |
| POST | /openapi/card/updateEmail/v1 | 更新邮箱 (无描述，方法名 updateEmail) |
| POST | /openapi/card/updateCardFee/v1 | 更新卡费用 (无描述，方法名 updateCardFee) |
| POST | /openapi/card/activeCard/v1 | 激活卡 (无描述，方法名 activeCard) |
| POST | /openapi/card/bindCard/v1 | 绑卡 (无描述，方法名 bindCard) |

#### CardInnerController（内部 RPC：卡管理）
类级前缀：`/feign/card`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/card/innerFreezeAllCard/v1 | 内部冻结全部卡 (无描述) |
| POST | /feign/card/updateCardPin/v1 | 更新卡 PIN (无描述) |
| GET | /feign/card/{threeCardId}/v1 | 按 threeCardId 查卡 (无描述) |
| GET | /feign/card/getByCardId/v1 | 按 cardId 查卡 (无描述) |
| POST | /feign/card/saveBankCardCompany/v1 | 保存银行卡公司 (无描述) |
| POST | /feign/card/saveBindBankCardCompany/v1 | 保存绑定银行卡公司 (无描述) |
| POST | /feign/card/updateCardSatusDesc/v1 | 更新卡状态描述 (无描述) |
| POST | /feign/card/addReduceBankCardStockStatement/v1 | 增减银行卡库存流水 (无描述) |
| POST | /feign/card/lockCard/v1 | 锁卡 (无描述) |
| POST | /feign/card/unLockCard/v1 | 解锁卡 (无描述) |
| POST | /feign/card/getCardPanHtmlCardNumber/v1 | 获取卡 PAN HTML/卡号 (无描述) |
| POST | /feign/card/updateCardStateMarking/v1 | 更新卡状态标记 (无描述) |
| POST | /feign/card/saveCompensationSchedule/v1 | 保存补偿计划 (无描述) |
| POST | /feign/card/editCompensationSchedule/v1 | 编辑补偿计划 (无描述) |
| POST | /feign/card/saveCardScheduledInfo/v1 | 保存卡定时任务信息 (无描述) |
| POST | /feign/card/saveCardScheduledDetailsBatch/v1 | 批量保存卡定时明细 (无描述) |
| POST | /feign/card/omsLogisticsShipped/v1 | OMS 物流发货 (无描述) |
| POST | /feign/card/companyCardMonthlyFeeRollback/v1 | 企业持卡月费回滚 (无描述) |

#### CardTradeInnerController（内部 RPC：卡交易查询）
类级前缀：`/feign/card/inner/transaction`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/card/inner/transaction/getListTransactions/v1 | 查询交易列表 (无描述) |
| POST | /feign/card/inner/transaction/getAllTransactions/v1 | 查询全部交易 (无描述) |
| POST | /feign/card/inner/transaction/getSingleTransaction/v1 | 查询单笔交易 (无描述) |
| POST | /feign/card/inner/transaction/list | 列表 (无描述) |
| POST | /feign/card/inner/transaction/{id} | 按 id 查询 (无描述) |

#### ApiCardInnerController（内部 RPC：对外卡操作的落地实现 + 回滚）
类级前缀：`/feign/card`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/card/submitCard/v1 | 提交开卡 (无描述) |
| POST | /feign/card/submitCardRollback/v1 | 提交开卡回滚 (无描述) |
| POST | /feign/card/rechargeCard/v1 | 卡充值 (无描述) |
| POST | /feign/card/rechargeCardRollback/v1 | 卡充值回滚 (无描述) |
| POST | /feign/card/destroyCard/v1 | 销卡 (无描述) |
| POST | /feign/card/destroyCardRollback/v1 | 销卡回滚 (无描述) |
| POST | /feign/card/freezeCard/v1 | 冻结卡 (无描述) |
| POST | /feign/card/unFreezeCard/v1 | 解冻卡 (无描述) |
| POST | /feign/card/getCardPanHtml/v1 | 获取卡 PAN HTML (无描述) |
| POST | /feign/card/respondTo3DSVerification/v1 | 3DS 验证响应 (无描述) |
| POST | /feign/card/updatePhone/v1 | 更新手机号 (无描述) |
| POST | /feign/card/updateEmail/v1 | 更新邮箱 (无描述) |
| POST | /feign/card/updateCardFee/v1 | 更新卡费用 (无描述) |
| POST | /feign/card/activeCard/v1 | 激活卡 (无描述) |
| POST | /feign/card/bindCard/v1 | 绑卡 (无描述) |
| POST | /feign/card/bindCardRollback/v1 | 绑卡回滚 (无描述) |

---

### 2.2 模块：tevau-nexus-query（查询服务）

#### QueryController（对外 OpenAPI：钱包/账单查询）
类级前缀：`/openapi/query`；@Api(value = "查询服务")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openapi/query/getCardAccountInfo/v1 | 查询企业钱包余额 |
| POST | /openapi/query/getBillPage/v1 | 企业查询账单列表 |
| POST | /openapi/query/getBillDetail/v1 | 企业查询账单详情 |

#### QueryCardController（对外 OpenAPI：卡信息查询）
类级前缀：`/openapi/query/card`；@Api(value = "查询卡服务")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openapi/query/card/getCardList/v1 | 获取客户银行卡信息列表 |
| POST | /openapi/query/card/getCardDetail/v1 | 获取客户银行卡信息详情 |
| POST | /openapi/query/card/getCardPin/v1 | 获取卡 PIN 码详情 |
| POST | /openapi/query/card/getCardLimitList/v1 | OpenApi 查询卡限额 |
| POST | /openapi/query/card/getTenantCardFeeList/v1 | OpenApi 查询卡交易手续费 |
| POST | /openapi/query/card/getCardLogistics/v1 | OpenApi 物流信息查询 |

#### QueryCardInnerController（内部 RPC：查询卡信息）
类级前缀：`/feign/query/card`；@Api(value = "查询卡信息")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/query/card/getCardList/v1 | 获取客户银行卡信息列表（与 QueryCardFeign 对应） |
| POST | /feign/query/card/getCardDetail/v1 | 获取客户银行卡信息详情 |
| POST | /feign/query/card/getCardPin/v1 | 获取卡 PIN 码详情 |
| POST | /feign/query/card/getCardLimitList/v1 | 查询卡限额 |
| POST | /feign/query/card/getTenantCardFeeList/v1 | 获取卡限额、费用 |
| POST | /feign/query/card/getCardLogistics/v1 | 查询物流信息 |

#### QueryInnerController（内部 RPC：用户/钱包/账单查询）
类级前缀：`/feign/query`；@Api(value = "用户信息")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/query/getCardAccountInfo/v1 | 查询企业钱包余额 |
| POST | /feign/query/getBillPage/v1 | 企业查询账单列表 |
| POST | /feign/query/getBillDetail/v1 | 企业查询账单详情 |

---

### 2.3 模块：tevau-nexus-user（用户 / KYC）

#### UserController（对外 OpenAPI：下游用户管理）
类级前缀：`/openapi/user`；@Api(value = "查询服务")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openapi/user/addUser/v1 | 创建企业下游用户 |
| POST | /openapi/user/getUserInfo/v1 | 查询指定企业下游用户信息 |

#### UserKycController（对外 OpenAPI：KYC）
类级前缀：`/openapi/kyc`；@Api(value = "查询服务")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openapi/kyc/submitKycData/v1 | kyc 认证 |
| POST | /openapi/kyc/getKycInfo/v1 | 获取 kyc 认证信息 |
| POST | /openapi/kyc/getKycUrl/v1 | 获取 KYC 链接地址 |
| POST | /openapi/kyc/getLevel2Result/v1 | 获取 KYC 二级验证结果 |

#### UserExternalController（对外/定时任务触发：KYC 与企业卡定时任务）
类级前缀：`/user/kyc`；@Api(value = "查询服务")
（注：源码中部分 test 任务接口被注释，下表只列未注释的）

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /user/kyc/scheduled/auditKycInfo/v1 | 定时任务：查询 kyc 第三方审核结果 |
| POST | /user/kyc/scheduled/companyCardCreateTask/v1 | 企业卡创建定时任务 (无描述) |
| POST | /user/kyc/scheduled/companyCardDestroyTask/v1 | 企业卡销卡定时任务 (无描述) |
| POST | /user/kyc/scheduled/companyCardRechargeTask/v1 | 企业卡充值定时任务 (无描述) |
| POST | /user/kyc/scheduled/tevauToOpenApiTask/v1 | Tevau → OpenApi 调拨定时任务 (无描述) |
| POST | /user/kyc/scheduled/openApiToTevauTask/v1 | OpenApi → Tevau 调拨定时任务 (无描述) |

#### ApiUserKycInnerController（内部 RPC：KYC）
类级前缀：`/feign/kyc`；@Api(value = "用户kyc信息")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/kyc/submitKycData/v1 | kyc 认证（与 ApiUserKycFeign 对应） |
| POST | /feign/kyc/getKycInfo/v1 | 获取 kyc 认证信息 |
| POST | /feign/kyc/getKycUrl/v1 | 获取 KYC 链接地址 |
| POST | /feign/kyc/getLevel2Result/v1 | 获取 KYC 二级验证结果 |

#### UserInnerController（内部 RPC：用户信息）
类级前缀：`/feign/user`；@Api(value = "用户信息")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /feign/user/getUserById | 获取用户信息 ById |
| GET | /feign/user/getUserByUserCode | 获取用户信息 ByUserCode |
| GET | /feign/user/getUserKycInfo | 获取用户 KYC 信息 |
| POST | /feign/user/updateKycInfo | 修改 kyc 信息 |
| POST | /feign/user/updateUserInfo/v1 | 更新用户基础信息 |
| GET | /feign/user/getFileUrl | 获取文件地址 |
| GET | /feign/user/updateUserKycAuditRecord | 修改 KYC 审核记录信息 |
| POST | /feign/user/addUser/v1 | 创建企业下游用户 |
| POST | /feign/user/getUserInfo/v1 | 查询指定企业下游用户信息 |
| GET | /feign/user/getCountryArea/v1 | 根据国家编号查询国家信息 |
| POST | /feign/user/userFeeRollback/v1 | 用户费用回滚 (无描述) |
| POST | /feign/user/doCompanyKycMonthlyFeeRollback/v1 | 企业 KYC 月费回滚 (无描述) |
| GET | /feign/user/getCountryCurrency/v1 | 获取国家币种代码 |
| GET | /feign/user/flushCountryCurrency/v1 | 刷新国家币种缓存 (无描述) |
| POST | /feign/user/saveKycScheduledService/v1 | 保存 KYC 提交审核扣费记录 |
| POST | /feign/user/editKycScheduledService/v1 | 保存/编辑 KYC 提交审核扣费记录 |
| POST | /feign/user/auditLeve1Data/v1 | kyc 审核 Level1 数据 |
| POST | /feign/user/auditLeve2Data/v1 | kyc 审核 Level2 数据 |

#### UserTestController（测试/回调测试）
类级前缀：`/user`；@Api(value = "用户信息")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /user/callbackTest | 回调测试 (无描述) |
| POST | /user/rampableCallbackTest | Rampable 回调测试 (无描述) |
| GET | /user/userTest | 用户测试 (无描述) |

---

### 2.4 模块：tevau-nexus-account（账户/记账 RPC）

#### CardAccountRpc（内部 RPC：卡账户记账）
类级前缀：`/account`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /account/card/cardAccountUndo | 卡账户记账撤销 (无描述) |
| POST | /account/card/cardAccounting | 卡账户记账 (无描述) |
| GET | /account/card/findCardAccountCount | 查询卡账户记账笔数 (无描述) |
| POST | /account/tenantAccountDetails | 租户账户明细 (无描述) |
| GET | /account/card/findCardAccountCountByTradeSn | 按交易号查卡账户记账笔数 (无描述) |
| POST | /account/card/changePaidAccount | 变更已付账户 (无描述) |

#### TenantAccountRpc（内部 RPC：租户账户记账）
类级前缀：`/tenant/account`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /tenant/account/tenantAccounting | 租户记账 (无描述) |
| POST | /tenant/account/getTenantAccounting | 查询租户记账 (无描述) |
| GET | /tenant/account/findTenantAccountCount | 查询租户账户记账笔数 (无描述) |
| GET | /tenant/account/findTenantAccountCountByTradeSn | 按交易号查租户账户记账笔数 (无描述) |
| POST | /tenant/account/tenantAccountUndo | 租户账户记账撤销 (无描述) |

#### TevauAccountRpc（内部 RPC：Tevau 账户记账）
类级前缀：`/tevau/account`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /tevau/account/accounting | Tevau 记账 (无描述) |
| POST | /tevau/account/changeAccount | 变更账户 (无描述) |
| POST | /tevau/account/changeAccountList | 批量变更账户 (无描述) |

#### TevauNexusAccountController（账户测试）
类级前缀：`/account`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /account/test | 测试接口 (无描述) |

---

### 2.5 模块：tevau-nexus-trade（交易 / 订单 / 账单 / 报表）

#### MockTransactionController（对外 OpenAPI：模拟交易，沙箱用）
类级前缀：`/openapi/trade`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openapi/trade/authorisation/v1 | 模拟授权 (无描述) |
| POST | /openapi/trade/clearing/v1 | 模拟清算 (无描述) |
| POST | /openapi/trade/refund/v1 | 模拟退款 (无描述) |
| POST | /openapi/trade/reversal/v1 | 模拟冲正 (无描述) |
| POST | /openapi/trade/auth/3ds/v1 | 模拟 3DS 授权 (无描述) |
| POST | /openapi/trade/auth/cardStatus/v1 | 模拟卡状态校验 (无描述) |

#### TevauNexusReapController（内部 RPC：Reap 卡组织回调）
类级前缀：`/trade/nexus`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /trade/nexus/callback | Reap 交易回调 (无描述) |

#### ReportDataController（内部 RPC：报表数据）
类级前缀：`/trade/report`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /trade/report/reportData | 报表数据 (无描述) |

#### ManualAdjustmentController（内部：人工调账）
类级前缀：`/inside/adjust`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /inside/adjust/adjustment | 人工调账 (无描述) |

#### TevauNexusTradeController（交易测试）
类级前缀：`/trade`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /trade/test | 测试 (无描述) |
| GET | /trade/test2 | 测试2 (无描述) |
| GET | /trade/test3 | 测试3 (无描述) |

#### NexusOrderInfoRpc（内部 RPC：订单信息）
类级前缀：`/trade/order`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /trade/order/saveOrder | 保存订单 (无描述) |
| POST | /trade/order/updateOrder | 更新订单 (无描述) |
| POST | /trade/order/updateOrderItem | 更新订单项 (无描述) |
| POST | /trade/order/getOrderInfo | 查询订单信息 (无描述) |
| POST | /trade/order/getOrderByTradeSnInfo | 按交易号查订单信息 (无描述) |

#### NexusBillingHistoryRpc（内部 RPC：账单历史）
类级前缀：`/trade/billing`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /trade/billing/saveBillingHistory | 保存账单历史 (无描述) |
| POST | /trade/billing/updateBillingHistory | 更新账单历史 (无描述) |
| POST | /trade/billing/saveBillingHistoryDetails | 保存账单历史明细 (无描述) |
| GET | /trade/billing/queryDetailsLast | 查询最新账单明细 (无描述) |
| GET | /trade/billing/queryHistoryByTxId | 按交易 ID 查账单历史 (无描述) |

#### TradeMessageRpc（内部 RPC：交易消息）
类级前缀：`/trade/message`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /trade/message/submitTransaction | 提交交易 (无描述) |
| POST | /trade/message/submitDelayTransaction | 提交延迟交易 (无描述) |
| POST | /trade/message/submitDelayMonitor | 提交延迟监控 (无描述) |
| POST | /trade/message/submitCallback | 提交回调 (无描述) |
| POST | /trade/message/updateTevauAccount | 更新 Tevau 账户 (无描述) |
| POST | /trade/message/clearing | 清算 (无描述) |

#### FeeRpc（内部 RPC：手续费）
类级前缀：`/trade/fee`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /trade/fee/tradeFee | 交易手续费计算 (无描述) |

#### TransExceptionRpc（内部 RPC：交易异常日志）
类级前缀：`/trade/logs`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /trade/logs/saveExceptionLogs | 保存交易异常日志 (无描述) |

#### TradeNotifyRpc（内部 RPC：异步通知）
类级前缀：`/trade/asyncNotify`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /trade/asyncNotify/notify | 异步通知 (无描述) |

#### NexusTenantCardFeeRpc（内部 RPC：租户卡费用）
类级前缀：`/trade/tenant/card/fee`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /trade/tenant/card/fee/saveOrUpdateTenantCardFee | 保存/更新租户卡费用 (无描述) |
| POST | /trade/tenant/card/fee/initTenantCardFee | 初始化租户卡费用 (无描述) |
| POST | /trade/tenant/card/fee/queryTenantCardFeeList | 查询租户卡费用列表 (无描述) |

#### TradeEventRpc（内部 RPC：交易事件）
类级前缀：`/trade/event`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /trade/event/saveEvent | 保存交易事件 (无描述) |
| POST | /trade/event/updateEvent | 更新交易事件 (无描述) |

#### TradeScheduleRpc（内部 RPC：交易调度）
类级前缀：`/trade/schedule`
（提取数据中仅见类级 @RequestMapping，无具体方法 mapping 行）

---

### 2.6 模块：tevau-nexus-settlement（结算 / 退款 RPC）

#### ReapSettlementRpc（内部 RPC：结算）
类级前缀：`/settlement`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /settlement/trade/settlement | 交易结算 (无描述) |

#### RefundRpc（内部 RPC：退款）
类级前缀：`/refund/trade`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /refund/trade/refund | 退款 (无描述) |

---

### 2.7 模块：tevau-nexus-webhook（Webhook）

#### TevauNexusWebHookOpenApi（对外 OpenAPI：Webhook 注册/查询/删除）
类级前缀：`/nexus/webhook/api`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /nexus/webhook/api/registerWebhook | 注册 Webhook (无描述) |
| GET | /nexus/webhook/api/queryWebHook | 查询 Webhook (无描述) |
| GET | /nexus/webhook/api/deleteWebHook | 删除 Webhook (无描述) |

#### WebhookRpc（内部 RPC：Webhook 通知）
类级前缀：`/web/hook`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /web/hook/notify | Webhook 通知（与 mq-consumer 的 WebHookFeign /web/hook/notify 对应） (无描述) |

---

### 2.8 模块：tevau-nexus-datacenter（数据中心 / 定时任务落地）

> 4 个控制器共用类级前缀 `/feign/dataCenter`（同前缀不同方法，均为内部 RPC）。

#### DataKycController（前缀 /feign/dataCenter）

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/dataCenter/auditKycInfo/v1 | 定时任务：查询 kyc 第三方审核结果（描述见 DataCenterFeign） |
| POST | /feign/dataCenter/resetKycValidateStatus/v1 | 重置 KYC 校验状态 (无描述) |

#### DataUpmsController（前缀 /feign/dataCenter）

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/dataCenter/tevauToOpenApiTask/v1 | 调拨从 Tevau 到 OpenApi (无描述，描述见 UpmsFeign) |
| POST | /feign/dataCenter/openApiToTevauTask/v1 | 调拨从 OpenApi 到 Tevau (无描述) |

#### DataInnerController（前缀 /feign/dataCenter）

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/dataCenter/doCompensationSchedule/v1 | 执行补偿计划 (无描述) |

#### DataChainAddressController（前缀 /feign/dataCenter）

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/dataCenter/topUpChainAddress/v1 | 链上地址充值 (无描述) |

#### DataFeeController（前缀 /feign/dataCenter）

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/dataCenter/companyKycMonthlyFeeTask/v1 | 定时任务：企业 KYC 月费扣费（描述见 DataCenterFeign） |
| POST | /feign/dataCenter/company3dsMonthlyFeeTask/v1 | 定时任务：企业 3DS 月费扣款（描述见 DataCenterFeign） |
| POST | /feign/dataCenter/companyCardMonthlyFeeTask/v1 | 企业持卡月费扣费定时任务 (无描述) |

#### DataCardCompanyController（前缀 /feign/dataCenter）

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /feign/dataCenter/companyCardCreateTask/v1 | 企业卡创建定时任务 (无描述) |
| POST | /feign/dataCenter/companyCardRechargeTask/v1 | 企业卡充值定时任务 (无描述) |
| POST | /feign/dataCenter/companyCardDestroyTask/v1 | 企业卡销卡定时任务 (无描述) |

---

### 2.9 模块：tevau-nexus-upms（运营后台 / 企业后台 / 管理）

#### UpmsInnerController（内部 RPC：后台内部服务）
类级前缀：`upms/feign`；@Api(value = "后台内部服务")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /upms/feign/getCompanyInfoList/v1 | 查询所有企业列表（描述见 UpmsFeign） |
| GET | /upms/feign/getCompanyConfigByTenantId/v1 | 查询企业回调通知信息 |
| POST | /upms/feign/getBusiConfigInfo/v1 | 查询系统业务配置 |
| POST | /upms/feign/getTNexusChainAddress/v1 | 查询企业信息-链上地址 |
| POST | /upms/feign/saveTNexusChainAddressRecord/v1 | 保存企业信息-重试失败链上地址记录 |
| POST | /upms/feign/updateChainAddressRecord/v1 | 链上地址记录失败次数累加 |
| POST | /upms/feign/tevauToOpenApiTask/v1 | 调拨从 Tevau 到 OpenApi |
| POST | /upms/feign/openApiToTevauTask/v1 | 调拨从 OpenApi 到 Tevau |
| POST | /upms/feign/chainAddressTopUp/v1 | 企业链上充值 |

#### UpmsCardScheduledController（客户管理列表 - 月费年费）
类级前缀：`/upms/cardScheduled`；@Api(tags = "客户管理列表")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/cardScheduled/qryCardScheduledPage | 查询月费年费记录列表 |
| GET | /upms/cardScheduled/export | 导出 |

#### TNexusBankCardBatchSaleLogController（中台批量出卡管理）
类级前缀：`/upms/card/bankCardBatchSaleLog`；@Api(tags = "中台批量出卡管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/card/bankCardBatchSaleLog/page | 分页 |
| POST | /upms/card/bankCardBatchSaleLog/add | 创建批量出卡记录 |

#### UserKycAuditRecordController（用户 KYC 认证审核记录）
类级前缀：`/upms/userKycAuditRecord`；@Api(tags = "用户kyc认证审核记录")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/userKycAuditRecord/page | 分页 |
| GET | /upms/userKycAuditRecord/getDetail/{id} | 获取详情 |
| POST | /upms/userKycAuditRecord/audit | 审核 |
| GET | /upms/userKycAuditRecord/auditTest | 审核（测试） |

#### KycAuditConfigController（KYC 审核配置）
类级前缀：`/upms/kycAuditConfig`；@Api(tags = "kyc审核配置")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /upms/kycAuditConfig/list | 列表 |
| POST | /upms/kycAuditConfig/update | 审核配置修改 |
| POST | /upms/kycAuditConfig/save | 新增 |

#### UpmsUserController（客户管理列表）
类级前缀：`/upms/user`；@Api(tags = "客户管理列表")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/user/page | 分页 |
| GET | /upms/user/getDetail/{id} | 获取详情 |
| POST | /upms/user/editUserStatus | 修改客户状态 |

#### AuthCallbackController（3DS 记录）
类级前缀：`/upms/authCallback`；@Api(tags = "3DS记录")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/authCallback/page | 分页 |

#### EnumerationController（枚举数据）
类级前缀：`/upms/sys/enum`；@Api(tags = "枚举数据")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET/POST | /upms/sys/enum/listByNames | 通过枚举名称查询 |
| GET/POST | /upms/sys/enum/all | 查询所有 |

#### UserSettingController（用户设置）
类级前缀：`/openadmin/userSetting`；@Api(value = "用户设置")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /openadmin/userSetting/getSettingStatus | 获取谷歌验证码状态 |

#### NexusExcelController（Excel 模板/导入）
类级前缀：`/upms`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /upms/downloadTemplate | 下载模板 (无描述) |
| POST | /upms/importExcel | 导入 Excel（multipart） (无描述) |

#### NexusPhysicalCardController（实体卡仓储）
类级前缀：`/upms/warehouse/physicalCard`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/warehouse/physicalCard/pageList | 实体卡分页列表 (无描述) |

#### NexusCardCSNController（卡 CSN 仓储）
类级前缀：`/upms/warehouse/csn`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/warehouse/csn/pageList | CSN 分页列表 (无描述) |
| GET | /upms/warehouse/csn/detailById/{serialNumber} | 按序列号查详情 (无描述) |

#### NexusCardLogisticsController（卡物流仓储）
类级前缀：`/upms/warehouse/logistics`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/warehouse/logistics/pageList | 物流分页列表 (无描述) |
| GET | /upms/warehouse/logistics/detailById/{id} | 按 id 查物流详情 (无描述) |
| POST | /upms/warehouse/logistics/confirmCardNumber | 确认卡号 (无描述) |
| POST | /upms/warehouse/logistics/shipped | 发货 (无描述) |
| POST | /upms/warehouse/logistics/updateLogisticsInfo | 更新物流信息 (无描述) |

#### NexusCardStockInfoController（卡库存信息）
类级前缀：`/upms/warehouse/stock`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/warehouse/stock/pageList | 库存分页列表 (无描述) |
| POST | /upms/warehouse/stock/save | 保存库存 (无描述) |
| GET | /upms/warehouse/stock/getCardTitleInventory/{cardTitle} | 按卡名查库存 (无描述) |
| POST | /upms/warehouse/stock/transfer | 库存调拨 (无描述) |

#### NexusBankCardCompanyController（银行卡公司仓储）
类级前缀：`/upms/warehouse/company`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/warehouse/company/pageList | 分页列表 (无描述) |

#### NexusCardTemplateController（卡模板）
类级前缀：`/upms/card/template`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/card/template/pageList | 卡模板分页列表 (无描述) |
| GET | /upms/card/template/getGroupByCardChannelTypeAndTitle | 按渠道类型和卡名分组查询 (无描述) |
| GET | /upms/card/template/getCardTitleList | 卡名列表 (无描述) |

#### LoginController（登录管理 - 后台/企业账户）
类级前缀：`/openadmin/sys`；@Api(tags = "登录管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openadmin/sys/userLogin | 登录 |
| POST | /openadmin/sys/userLoginPass | 登录 |
| POST | /openadmin/sys/userAccount | 登录账户 |
| POST | /openadmin/sys/userDetail | 登录账户（详情） |
| POST | /openadmin/sys/changePass | 修改密码，验证码要根据登入来获取 |
| POST | /openadmin/sys/updatePass | 设置修改密码，验证码要根据登入来获取 |
| POST | /openadmin/sys/updateEmail | 设置修改邮箱 |
| POST | /openadmin/sys/logout | 退出 |
| POST | /openadmin/sys/companyLogin | 企业账户登录接口 |
| POST | /openadmin/sys/userRegister | 注册 |
| POST | /openadmin/sys/getAsyncRoutes | getAsyncRoutes |

#### MiddleController（登录管理 - 中台 token）
类级前缀：`/sys`；@Api(tags = "登录管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /sys/middleLogin | 登录 |
| POST | /sys/userToken | 同步 token |
| POST | /sys/logoutToken | 退出 |

#### SysParamsController（参数管理）
类级前缀：`sys/params`；@Api(tags = "参数管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/params/page | 分页 |
| GET | /sys/params/{id} | 信息 |
| POST | /sys/params | 保存 |
| PUT | /sys/params | 修改 |
| DELETE | /sys/params | 删除 |
| GET | /sys/params/export | 导出 |

#### SysDeptController（部门管理）
类级前缀：`/sys/dept`；@Api(tags = "部门管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/dept/list | 列表 |
| GET | /sys/dept/{id} | 信息 |
| POST | /sys/dept | 保存 |
| PUT | /sys/dept | 修改 |
| DELETE | /sys/dept/{id} | 删除 |

#### SysGroupUserController（群组用户管理）
类级前缀：`/sys/groupUser`；@Api(tags = "群组用户管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/groupUser/page | 分页 |
| GET | /sys/groupUser/list | 列表 |
| GET | /sys/groupUser/{id} | 信息 |
| POST | /sys/groupUser | 保存 |
| PUT | /sys/groupUser | 修改 |
| DELETE | /sys/groupUser | 删除 |

#### SysDictTypeController（字典类型）
类级前缀：`sys/dict/type`；@Api(tags = "字典类型")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/dict/type/page | 字典类型 |
| GET | /sys/dict/type/{id} | 信息 |
| POST | /sys/dict/type | 保存 |
| PUT | /sys/dict/type | 修改 |
| DELETE | /sys/dict/type | 删除 |
| GET | /sys/dict/type/all | 所有字典数据 |

#### SysGroupController（群组管理）
类级前缀：`/sys/group`；@Api(tags = "群组管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/group/page | 分页 |
| GET | /sys/group/list | 列表 |
| GET | /sys/group/{id} | 信息 |
| POST | /sys/group | 保存 |
| PUT | /sys/group | 修改 |
| DELETE | /sys/group | 删除 |

#### SysUserController（用户管理）
类级前缀：`/sys/user`；@Api(tags = "用户管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/user/page | 分页 |
| GET | /sys/user/{id} | 信息 |
| GET | /sys/user/info | 登录用户信息 |
| PUT | /sys/user/password | 修改密码 |
| POST | /sys/user | 保存 |
| PUT | /sys/user | 修改 |
| DELETE | /sys/user | 删除 |
| GET | /sys/user/export | 导出 |
| GET | /sys/user/clearGaInfo/{userId} | 清除谷歌验证器信息 |

#### SysMenuController（菜单管理）
类级前缀：`/sys/menu`；@Api(tags = "菜单管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/menu/nav | 导航 |
| GET | /sys/menu/permissions | 权限标识 |
| GET | /sys/menu/list | 列表 |
| GET | /sys/menu/{id} | 信息 |
| POST | /sys/menu | 保存 |
| PUT | /sys/menu | 修改 |
| DELETE | /sys/menu/{id} | 删除 |
| GET | /sys/menu/select | 角色菜单权限 |

#### IndexController（首页）
（无类级 @RequestMapping）

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | / | 首页 (无描述) |

#### SysRoleController（角色管理）
类级前缀：`/sys/role`；@Api(tags = "角色管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/role/page | 分页 |
| GET | /sys/role/list | 列表 |
| GET | /sys/role/{id} | 信息 |
| POST | /sys/role | 保存 |
| PUT | /sys/role | 修改 |
| DELETE | /sys/role | 删除 |

#### SysDictDataController（字典数据）
类级前缀：`sys/dict/data`；@Api(tags = "字典数据")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/dict/data/page | 字典数据 |
| GET | /sys/dict/data/{id} | 信息 |
| POST | /sys/dict/data | 保存 |
| PUT | /sys/dict/data | 修改 |
| DELETE | /sys/dict/data | 删除 |

#### SysLogLoginController（登录日志）
类级前缀：`sys/log/login`；@Api(tags = "登录日志")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/log/login/page | 分页 |
| GET | /sys/log/login/export | 导出 |

#### SysLogErrorController（异常日志）
类级前缀：`sys/log/error`；@Api(tags = "异常日志")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/log/error/page | 分页 |
| GET | /sys/log/error/export | 导出 |

#### SysLogOperationController（操作日志）
类级前缀：`sys/log/operation`；@Api(tags = "操作日志")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /sys/log/operation/page | 分页 |
| GET | /sys/log/operation/export | 导出 |

#### TNexusCompanyConfigController（企业接口密钥管理）
类级前缀：`/openadmin/config`；@Api(tags = "企业接口密钥管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /openadmin/config/keyValue/{type} | 查询企业沙箱/生产 KEY（type=1 沙箱，type=2 生产） |
| POST | /openadmin/config/list | 分页 |

#### TNexusCompanyIntroduceController（API 管理 - 企业介绍/KYB）
类级前缀：`/openadmin/admin/introduce`；@Api(tags = "API管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openadmin/admin/introduce/update | 企业列表修改 |
| POST | /openadmin/admin/introduce/save | 企业介绍保存，生成对应的 KYB 租户信息 |
| POST | /openadmin/admin/introduce/uploadFileInfo | 上传文件信息 |
| DELETE | /openadmin/admin/introduce | 企业介绍删除 |
| GET | /openadmin/admin/introduce/getDetail/{id} | 查询企业介绍 |
| POST | /openadmin/admin/introduce/detailByUserId | 用户企业的介绍信息 |

#### TNexusTransactionController（预收款 - 已整体注释停用）
源码中类级 @Api / @RequestMapping 被注释（`//@RequestMapping("/upms/transaction")`），方法 @PostMapping("page")/("export") 仍在但**当前未对外暴露**（无类级映射）。记录如下：

| HTTP | 完整路径(注释前) | 功能描述 |
|---|---|---|
| POST | (/upms/transaction)/page | 分页（控制器已注释停用） |
| POST | (/upms/transaction)/export | 导出（控制器已注释停用） |

#### TNexusFeeConfigController（平台费用配置表）
类级前缀：`/openadmin/admin/feeConfig`；@Api(tags = "平台费用配置表")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openadmin/admin/feeConfig/queryList | 查询 |
| POST | /openadmin/admin/feeConfig/update | 企业费率修改 |
| POST | /openadmin/admin/feeConfig/save | 企业费率新增 |

#### TNexusCountryAreaController（国家数字代码）
类级前缀：`/openadmin/admin/area`；@Api(tags = "国家数字代码")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openadmin/admin/area/query | 查询国家地址 |

#### TNexusCompanyIpController（IP 白名单管理）
类级前缀：`/openadmin/admin/ip`；@Api(tags = "IP")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openadmin/admin/ip/page | 分页 |
| POST | /openadmin/admin/ip/update | IP 列表修改 |
| POST | /openadmin/admin/ip/save | IP 列表新增 |
| POST | /openadmin/admin/ip/delete | IP 删除 |

#### TNexusDictionaryController（字典）
类级前缀：`/openadmin/admin/dictionary`；@Api(tags = "字典")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openadmin/admin/dictionary/query | 查询字典 |

#### TNexusKybManage（合作方管理 / KYB）
类级前缀：`/upms/kyb/manage`；@Api(tags = "合作方管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/kyb/manage/userPage | 分页 |
| POST | /upms/kyb/manage/auditPage | 分页 |
| POST | /upms/kyb/manage/detailByUserId | 用户企业的介绍信息 |
| POST | /upms/kyb/manage/kybAudit | KYB 审核 |
| POST | /upms/kyb/manage/tenantPage | 分页 |
| POST | /upms/kyb/manage/permissPage | 分页 |
| POST | /upms/kyb/manage/permissSave | 新增关联 |
| POST | /upms/kyb/manage/permissDelete | 删除关联 |

#### TNexusPrefundHistoryController（预收款历史）
类级前缀：`/openadmin/upms/prefundHistory`；@Api(tags = "预收款")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openadmin/upms/prefundHistory/page | 分页 |
| GET | /openadmin/upms/prefundHistory/export | 导出 |
| POST | /openadmin/upms/prefundHistory/imagData | 分页（图表/汇总数据） |

#### GoogleAuthenticatorController（谷歌验证码）
类级前缀：`/openadmin/ga`；@Api(value = "谷歌验证码")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| GET | /openadmin/ga/generateGoogleToken | 生成谷歌验证码 |
| POST | /openadmin/ga/bindGoogleToken | 绑定谷歌验证码 |
| POST | /openadmin/ga/updateSettingStatus | 用户开启关闭谷歌验证 |
| POST | /openadmin/ga/updateGoogleToken | 修改谷歌验证器 token |

#### TNexusChainAddressController（企业链上地址）
类级前缀：`/openadmin/admin/chainAddre`；@Api(tags = "企业链上地址")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openadmin/admin/chainAddre/page | 分页 |
| POST | /openadmin/admin/chainAddre/rechargeAmt | 企业充值 |
| POST | /openadmin/admin/chainAddre/rechargeAmtMQ | 模拟接口区块链充值 |

#### TNexusApiInfoController（API 管理）
类级前缀：`/admin/apiInfo`；@Api(tags = "API管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /admin/apiInfo/page | 分页 |
| POST | /admin/apiInfo/update | API 列表修改 |
| POST | /admin/apiInfo/save | API 列表新增 |
| DELETE | /admin/apiInfo | 删除 |
| GET | /admin/apiInfo/test | 分页（test） |

#### TNexusBusiConfigController（系统配置表）
类级前缀：`/upms/busiConfig`；@Api(tags = "系统配置表")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /upms/busiConfig/page | 分页 |
| POST | /upms/busiConfig/add | 系统配置表-添加 |
| POST | /upms/busiConfig/edit | 系统配置表-编辑 |

#### TNexusCompanyInfoController（API 管理 - 企业信息/租户）
类级前缀：`/openadmin/admin`；@Api(tags = "API管理")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openadmin/admin/page | 分页 |
| POST | /openadmin/admin/update | 企业列表修改 |
| POST | /openadmin/admin/save | 企业列表新增 |
| POST | /openadmin/admin/saveTenant | KYB 终审完成，创建租户 |
| DELETE | /openadmin/admin | 企业删除 |
| GET | /openadmin/admin/getDetail/{id} | 查询企业详情 |
| GET | /openadmin/admin/getCompanyInfo | 查询企业详情 |
| GET | /openadmin/admin/getCompanyUser | 查询当前登录用户授权企业列表 |
| POST | /openadmin/admin/captcha | 验证码 |

#### NexusBillingHistoryController（预收款，交易报表）★客服可用
类级前缀：`/openadmin/upms/transaction`；@Api(tags = "预收款,交易报表")

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openadmin/upms/transaction/page | 分页（交易/账单报表） |
| GET | /openadmin/upms/transaction/export | 导出 |
| POST | /openadmin/upms/transaction/orderPage | 分页（订单列表） |
| GET | /openadmin/upms/transaction/orderExport | 导出（订单） |

---

### 2.10 模块：tevau-nexus-job（XXL-Job 调度）

#### TestController（链上充值任务触发）
类级前缀：`/openAdmin/topup`

| HTTP | 完整路径 | 功能描述 |
|---|---|---|
| POST | /openAdmin/topup/topUpChainAddress | 链上地址充值 (无描述) |

---

### 2.11 模块：tevau-nexus-gateway（网关）

网关层不暴露业务接口，负责签名校验、参数加解密、限流、tenant_id 解析与透传。
提取数据中仅有一个工具类内的测试映射：`TevauTestHttpUtils` → `POST /callbackTest`（回调测试工具，非业务接口）。

---

## 3. 对「客服 AI 查 BU 数据」有用的接口 / 模块

客服 AI 的核心场景是：根据企业合作伙伴（BU）的提问，查订单 / 交易 / 账单 / 卡状态 / KYC 状态 / 请求日志。以下接口/模块**直接相关**，按优先级排列：

### 3.1 最直接可用（查询类，对外或后台只读）

| 接口/模块 | 路径 | 用途 |
|---|---|---|
| **NexusBillingHistoryController** | /openadmin/upms/transaction/page、/orderPage、/export、/orderExport | **交易报表 + 订单列表**，后台维度按 tenant 查 BU 的交易和订单，客服查"某笔交易/订单"首选 |
| **QueryController** | /openapi/query/getBillPage/v1、/getBillDetail/v1、/getCardAccountInfo/v1 | 企业账单列表/详情、企业钱包余额 |
| **QueryCardController** | /openapi/query/card/getCardList/v1、/getCardDetail/v1、/getCardPin/v1、/getCardLimitList/v1、/getTenantCardFeeList/v1、/getCardLogistics/v1 | 卡列表/详情/PIN/限额/手续费/物流 —— 客服查"卡状态/卡限额/卡物流" |
| **QueryInnerController** | /feign/query/getCardAccountInfo/v1、/getBillPage/v1、/getBillDetail/v1 | 上面 OpenAPI 的内部实现，AI 若走内部链路可直接用 |
| **QueryCardInnerController** | /feign/query/card/* | 卡信息内部查询实现 |

### 3.2 交易/订单/账单底层数据（内部 RPC，适合后端代 AI 取数）

| 接口/模块 | 路径 | 用途 |
|---|---|---|
| **NexusOrderInfoRpc** | /trade/order/getOrderInfo、/getOrderByTradeSnInfo | 按订单号/交易号查订单 —— 客服查"我那笔下单怎么了" |
| **NexusBillingHistoryRpc** | /trade/billing/queryHistoryByTxId、/queryDetailsLast | 按交易 ID 查账单历史/最新明细 |
| **CardTradeInnerController** | /feign/card/inner/transaction/getListTransactions/v1、/getAllTransactions/v1、/getSingleTransaction/v1 | 卡交易流水（列表/全部/单笔） —— 客服查"这笔扣款是什么" |
| **TransExceptionRpc** | /trade/logs/saveExceptionLogs | 交易异常日志（写入端；查异常原因时关联的数据源） |

### 3.3 状态/审核类（辅助定位问题）

| 接口/模块 | 路径 | 用途 |
|---|---|---|
| **UserKycController / ApiUserKycInnerController** | /openapi/kyc/getKycInfo/v1、/getLevel2Result/v1 等 | 查 BU 下游用户 KYC 状态/结果 —— 客服查"为什么我的用户开不了卡（KYC 没过）" |
| **UserKycAuditRecordController** | /upms/userKycAuditRecord/page、/getDetail/{id} | KYC 审核记录（后台），定位审核进度/驳回原因 |
| **AuthCallbackController** | /upms/authCallback/page | 3DS 记录，查"3DS 验证失败"类问题 |
| **CardInnerController / ApiCardController** | /feign/card/getByCardId/v1、/{threeCardId}/v1、/openapi/card/* | 查单卡状态、冻结/锁卡状态 |
| **UpmsUserController** | /upms/user/page、/getDetail/{id} | 后台查客户（BU 下游用户）状态 |

### 3.4 请求日志类

提取数据中 OpenAPI 调用的「请求日志」未见独立的查询 Controller（网关层 `BaseRequestGlobalFilter` / `RequestModifyFilter` 负责记录，但没有暴露查询接口）。后台侧最接近的是：
- **SysLogOperationController**（/sys/log/operation/page）：后台操作日志
- **SysLogErrorController**（/sys/log/error/page）：异常日志
- **SysLogLoginController**（/sys/log/login/page）：登录日志
这些是**运营后台自身的操作/异常/登录日志**，不是 BU 的 OpenAPI 调用日志。若客服 AI 需要"BU 的某次 API 请求记录"，当前提取范围内**没有现成查询接口**，需另查网关日志/数据落库（需进一步确认，提取数据中无此 Controller）。

---

## 4. 备注与不确定项

- `tevau-nexus-account/TevauNexusAccountController` 与 `CardAccountRpc` 都用了类级 `/account` 前缀；CardAccountRpc 的方法路径带 `/card/...`、`/tenantAccountDetails`，两者实际不冲突。
- `TradeScheduleRpc`（/trade/schedule）在提取数据中只有类级映射、无方法级 mapping，未列具体接口。
- `EnumerationController` 的 `listByNames`/`all` 用 `@RequestMapping` 未指定 method，按惯例 GET/POST 均可。
- `I18nController`、`TNexusTransactionController` 在源码中被整体注释，已标注停用。
- 大量 `-common` 包下的 `XxxFeign.java` 是 Feign 客户端声明，与对应 `-server` 控制器一一对应，未重复计数。
- 凡标 **(无描述)** 的接口，提取数据中确实没有 @ApiOperation，描述系根据方法名/路径推断，未编造业务语义。
