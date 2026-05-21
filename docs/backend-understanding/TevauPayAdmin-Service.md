# TevauPayAdmin-Service 接口地图（管理后台后端）

> 全量接口地图，覆盖 152 个 Controller。功能描述优先取自 `@ApiOperation` 中文原文；无注解的标注 `(无描述)`。
> 路径为「类级 `@RequestMapping` 前缀 + 方法级映射」拼接结果；个别 Controller 无类级前缀，方法上写的就是完整路径。

## 1. 服务概述

TevauPayAdmin-Service 是 Tevau 的**管理后台后端**，供内部运营、客服、风控、财务、营销团队使用（不是面向 C 端用户的 App 后端）。它聚合了用户/客户管理、银行卡管理、交易与退款处理、KYC 审核、工单类审核流程、风控黑白名单、财务对账与报表、营销活动/积分/返佣、商城订单、系统设置等业务能力。大量写操作通过 Feign 调用下游微服务（卡管理服务、用户服务、交易服务、法币服务、账户服务等）完成。

### 鉴权体系

后台采用独立的**管理员登录体系**，与 C 端用户体系分离：

- 权限模型基于 `sys_user`（管理员账号）/ `sys_role`（角色）/ `sys_menu`（菜单与权限标识）/ `sys_dept`（部门），即标准 RBAC。
- 技术栈：**Apache Shiro + OAuth2 Token**。登录流程：`LoginController` 先发验证码（`captcha`），再校验账号密码（`login`）下发 token；后续请求由 `Oauth2Filter` + `Oauth2Realm` 校验 token 并加载 `UserDetail` 权限。
- 密码使用 **BCrypt** 加盐哈希（`BCryptPasswordEncoder`）。
- 数据权限：`@DataFilter` 注解 + `DataFilterAspect`/`DataScope` 实现按部门的数据范围隔离。
- 安全过滤：`XssFilter`/`SqlFilter`/`TokenFilter` 做 XSS、SQL 注入、token 拦截。
- 登录与操作留痕：`SysLogLogin`（登录日志）、`SysLogOperation`（操作日志）、`UserLoginRecord`（C 端用户登录 IP 记录）。

---

## 2. 业务域分组总览

| 业务域 | 主要 Controller |
|--------|----------------|
| 鉴权与系统设置 | LoginController, SysUserController, SysRoleController, SysMenuController, SysDeptController, SysDictTypeController, SysDictDataController, SysParamsController, I18nController, ImageGalleryController, EnumerationController, IndexController, SysOssController, CommonController |
| 客户（C 端用户）管理 | TevaupayUserController, UserScriptController, GrayUserConfigController, UserLoginRecordController, ThirdLoginController, UserKycController, BankUserReceiveAddressController, UserCertificationRecordController |
| 卡管理 | UserBankCardController, CustomCardSerialNumberController, BankCardTemplateController, BankCardTemplatePersonalizationController, CardQuotaConfigController, BankCardStockQuantityController, CardFreezeHistoryController, BankCardFailureLogsController, PhysicalCardRecordsController, TevaupayAuthCallbackController, CardInactiveRepaymentOrderController |
| 卡物流 | BankCardLogisticsController, BankCardLogisticsBatchOperationController |
| 交易与退款 | CardRechargeRecordsController, CardTransactionRecordController, OrderRefundController, TransRefundController, TransExceptionController, TransLogController, AdviceRefundController, CardBalanceAdjustRecordController, SxRawDataLogController, DataCardTradeController, DataCustTradeController |
| 业务订单 / 风控审核 | BusinessOrderController, BusinessOrderAuditController, RestrictConfigController |
| KYC 审核 | UserKycAuditRecordController, KycAuditConfigController, FiatUSDKycReviewController |
| 法币（Fiat USD） | FiatOrderController, FiatConversionController, FiatUSDRefundController, FiatUsdRfiController, FiatUSDKycReviewController, FiatLimitController |
| 账单 / 财务对账 | BillController, EeBillController, ReapBillController, CardBillController, SXCardBillController, 以及 finance.* 全套（AccountRecordController, CardConsumeBillController, CardAccountOfflineRecordController, AccountOfflineController, DataOfflineAdjustmentRecordController, DataLegalTenderBankController, DataLegalTenderRecordController, FinanceWhitelistController, DataIncomeReportController, DataOutflowReportController, DataDailyTotalController, DataFinancePlatformController, AccountOtherController, AccountPlatformController, AccountDailyInfoController, AccountChannelController） |
| 费用配置 | TransactionFeeConfigController, ChannelFeeConfigController, MonthlyFeeController, MonthlyFeeDetailsController, PlatformRechargeExchangeRateController |
| 营销活动 | ActivityController, ActivityPeriodsController, ActivityRankingController, ActivityAccountRechargeController, ActivityChrisBlacklistController, ZnqRewardController, VoucherController, DiscountCodeConfigController, DiscountCodeUsageController |
| 积分系统 | Points* 系列 16 个 Controller |
| 返佣 | RebateConfigController, RebateRecordController, RebateDailyReportController, RebateCommDailySumController |
| 理财 | Financing* 系列 10 个 Controller |
| 商城 | MallProductController, MallOrderManagementController, MallCardSubOrderController, MallNoncardSubOrderController |
| 任务系统 | TaskConfigController, TaskConfigLanController, TaskUserRecordController, TaskExcelListController, DailyTaskCompletionLogController |
| 消息中心 | MsgController, MsgEmailTempController, MsgEmailTempAdminController |
| 内容运营 | BlogManageController, WebsiteVerificationController, BannerConfigController, ExplorePageAdminController, FunctionEntryController, FunctionCategoryController, FunctionI18nController |
| 文件 | FileRecordController |
| 第三方对接 | ReapController, BinanceOrderController |
| 国家地区 | CountryAreaController |
| 系统日志 / 定时任务 | SysLogOperationController, SysLogErrorController, SysLogLoginController, TevaupayLogOperationController, ScheduleJobController, ScheduleJobLogController, DataDailyReportController |

---

## 3. 各业务域接口明细

### 3.1 鉴权与系统设置

#### LoginController — 登录管理（无类级前缀）
- `GET captcha` — 验证码
- `POST login` — 登录
- `POST logout` — 退出

#### SysUserController — 用户管理（管理员账号）`/sys/user`
- `GET /sys/user/page` — 分页
- `GET /sys/user/{id}` — 信息
- `GET /sys/user/info` — 登录用户信息
- `PUT /sys/user/password` — 修改密码
- `POST /sys/user` — 保存
- `PUT /sys/user` — 修改
- `DELETE /sys/user` — 删除
- `GET /sys/user/export` — 导出

#### SysRoleController — 角色管理 `/sys/role`
- `GET /sys/role/page` — 分页
- `GET /sys/role/list` — 列表
- `GET /sys/role/{id}` — 信息
- `POST /sys/role` — 保存
- `PUT /sys/role` — 修改
- `DELETE /sys/role` — 删除

#### SysMenuController — 菜单管理 `/sys/menu`
- `GET /sys/menu/nav` — 导航
- `GET /sys/menu/permissions` — 权限标识
- `GET /sys/menu/list` — 列表
- `GET /sys/menu/{id}` — 信息
- `POST /sys/menu` — 保存
- `PUT /sys/menu` — 修改
- `DELETE /sys/menu/{id}` — 删除
- `GET /sys/menu/select` — 角色菜单权限

#### SysDeptController — 部门管理 `/sys/dept`
- `GET /sys/dept/list` — 列表
- `GET /sys/dept/{id}` — 信息
- `POST /sys/dept` — 保存
- `PUT /sys/dept` — 修改
- `DELETE /sys/dept/{id}` — 删除

#### SysDictTypeController — 字典类型 `sys/dict/type`
- `GET sys/dict/type/page` — 字典类型
- `GET sys/dict/type/{id}` — 信息
- `POST sys/dict/type` — 保存
- `PUT sys/dict/type` — 修改
- `DELETE sys/dict/type` — 删除
- `GET sys/dict/type/all` — 所有字典数据

#### SysDictDataController — 字典数据 `sys/dict/data`
- `GET sys/dict/data/page` — 字典数据
- `GET sys/dict/data/{id}` — 信息
- `POST sys/dict/data` — 保存
- `PUT sys/dict/data` — 修改
- `DELETE sys/dict/data` — 删除

#### SysParamsController — 参数管理 `sys/params`
- `GET sys/params/page` — 分页
- `GET sys/params/{id}` — 信息
- `POST sys/params` — 保存
- `PUT sys/params` — 修改
- `DELETE sys/params` — 删除
- `GET sys/params/export` — 导出

#### I18nController — 国际化服务 `/sys/i18n`
- `POST /sys/i18n/page` — (无描述)
- `POST /sys/i18n/save` — (无描述)
- `POST /sys/i18n/update` — (无描述)
- `DELETE /sys/i18n/delete/{configId}` — (无描述)
- `POST /sys/i18n/i18nRefresh` — (无描述)
- `GET /sys/i18n/lockCache` — (无描述)
- `GET /sys/i18n/unLockCache` — (无描述)

#### ImageGalleryController — 图片库 `/sys/gallery`
- `POST /sys/gallery/page` — 分页
- `GET /sys/gallery/listByType/{type}` — 通过类型返回图片库
- `POST /sys/gallery/save` — 新增
- `POST /sys/gallery/update` — 修改
- `DELETE /sys/gallery/delete/{id}` — 删除

#### EnumerationController — 枚举数据 `/sys/enum`
- `GET/POST /sys/enum/listByNames` — 通过枚举名称查询
- `GET/POST /sys/enum/all` — 查询所有

#### SysOssController — 文件上传 `sys/oss`
- `GET sys/oss/page` — 分页
- `GET sys/oss/info` — 云存储配置信息
- `POST sys/oss` — 保存云存储配置信息
- `POST sys/oss/upload` — 上传文件
- `DELETE sys/oss` — 删除

#### CommonController — 通用 `/common`
- `GET /common/export` — 文件导出

#### IndexController — 首页（无 @Api）
- `GET /` — (无描述)

---

### 3.2 客户（C 端用户）管理

#### TevaupayUserController — 客户信息 `/biz/tevaupayUser`
- `POST /biz/tevaupayUser/page` — 分页
- `GET /biz/tevaupayUser/getDetail/{id}` — 详情
- `POST /biz/tevaupayUser/updateInviteCode` — 修改邀请码
- `POST /biz/tevaupayUser/updateStatus` — 修改用户状态
- `POST /biz/tevaupayUser/updateInvitationLevel` — 修改邀请等级
- `POST /biz/tevaupayUser/signOff/{id}` — 注销用户
- `POST /biz/tevaupayUser/updateTag` — 修改标签
- `GET /biz/tevaupayUser/clearGaInfo/{userId}` — 清除谷歌验证器信息
- `GET /biz/tevaupayUser/cardTemplateCodeList` — 用户编号下拉列表

#### UserScriptController — 用户运营脚本 `/biz/userScript`
- `POST /biz/userScript/updateUserSuperior` — 调整用户上级信息
- `POST /biz/userScript/queryUserHierarchy` — 查询用户层级关系树（up=所有上级链路 / down=所有下级子树）

#### GrayUserConfigController — 灰度用户配置 `biz/grayUserConfig`
- `GET/POST biz/grayUserConfig/refreshCache` — (无描述)
- `GET/POST biz/grayUserConfig/addMember` — (无描述)
- `GET/POST biz/grayUserConfig/removeMember` — (无描述)
- `POST biz/grayUserConfig/page` — 分页查询灰度白名单
- `POST biz/grayUserConfig/addMembersByUser` — 批量添加灰度白名单（用户友好版）
- `POST biz/grayUserConfig/removeMembersByUser` — 批量移除灰度白名单（用户友好版）
- `POST biz/grayUserConfig/removeMemberById` — 按记录ID移除灰度白名单（用于用户已注销但记录仍存在的场景）

#### UserLoginRecordController — 注册登录 IP 的记录 `/user/loginRecord`
- `POST /user/loginRecord/page` — 分页
- `GET /user/loginRecord/loginRecordExport` — 注册登录IP的记录导出

#### ThirdLoginController — 第三方登录控制器 `/third/login`
- `POST /third/login/page` — 第三方账号信息分页
- `GET /third/login/detail` — 第三方账号信息详情
- `GET /third/login/unbind` — 解绑三方账号
- `POST /third/login/logPage` — 第三方账号信息分页

#### UserKycController — 操作日志（KYC）`sys/user/kyc`
- `GET sys/user/kyc/page` — 分页

#### BankUserReceiveAddressController — 客户收获地址管理 `/biz/userReceiveAddress`
- `POST /biz/userReceiveAddress/page` — 分页

#### UserCertificationRecordController — 三方认证记录 `/biz/userCertification`
- `POST /biz/userCertification/page` — 分页

---

### 3.3 卡管理

#### UserBankCardController — 银行卡信息 `/biz/userBankCard`
- `POST /biz/userBankCard/page` — 分页
- `GET /biz/userBankCard/export` — 导出
- `GET /biz/userBankCard/getDetail/{id}` — 详情
- `POST /biz/userBankCard/updateCardStatus` — 修改状态
- `GET /biz/userBankCard/downloadImportAgentTemplate` — 下载代理商导入模板
- `POST /biz/userBankCard/importAgentCard` — 导入代理卡
- `GET /biz/userBankCard/cancelCard` — 注销卡
- `GET /biz/userBankCard/getBalance/{id}` — 获取卡余额
- `GET /biz/userBankCard/unlock/{id}` — 解锁卡
- `POST /biz/userBankCard/resetCardPin` — 重置卡pin
- `GET /biz/userBankCard/getTokenList` — 获取token集合
- `GET /biz/userBankCard/getCardNumber3dsDetail` — 获取卡3ds详情
- `GET /biz/userBankCard/updateCardConfiguration` — 更新卡配置信息
- `GET /biz/userBankCard/getCardConfiguration` — 获取卡配置信息
- `GET /biz/userBankCard/cancelCardBatch` — 注销卡批量-脚本代码
- `GET /biz/userBankCard/queryCardBalance` — 查询余额-脚本代码
- `POST /biz/userBankCard/getVisaCurrencyExchangeRates` — 查询汇率信息
- `POST /biz/userBankCard/updateCardTokenStatus` — 修改Token状态

#### CustomCardSerialNumberController — 自定义卡序号 `/biz/customCardSerialNumber`
- `POST /biz/customCardSerialNumber/page` — 分页
- `GET /biz/customCardSerialNumber/downloadImportTemplate` — 下载模板
- `POST /biz/customCardSerialNumber/import` — 导入
- `GET /biz/customCardSerialNumber/getCardInfoBySerialNumber/{serialNumber}` — 根据实体卡序号，获取卡号和颜色

#### BankCardTemplateController — 卡模板信息 `/biz/cardTemplate`
- `POST /biz/cardTemplate/page` — 分页
- `GET /biz/cardTemplate/getDetail/{id}` — 详情
- `POST /biz/cardTemplate/save` — 新增
- `POST /biz/cardTemplate/update` — 修改
- `GET /biz/cardTemplate/getCascadeDataByPlatformAndTitle` — 根据卡方、卡头，获取卡模板联动数据
- `GET /biz/cardTemplate/getCardPlatformSelectionList` — 卡方下拉列表
- `GET /biz/cardTemplate/getCardTemplateTitleSelectionList` — 卡头下拉列表
- `GET /biz/cardTemplate/getByCardCode/{cardCode}` — 通过卡编号，获取卡模板信息
- `GET /biz/cardTemplate/cardTemplateCodeList` — 卡编号下拉列表
- `POST /biz/cardTemplate/refreshAllCache` — 刷新缓存

#### BankCardTemplatePersonalizationController — 卡模板个性化信息 `/biz/cardTemplatePersonalization`
- `POST /biz/cardTemplatePersonalization/page` — 分页
- `POST /biz/cardTemplatePersonalization/save` — 新增
- `POST /biz/cardTemplatePersonalization/update` — 修改
- `DELETE /biz/cardTemplatePersonalization/delete/{id}` — 删除

#### CardQuotaConfigController — 卡限额配置 `/card/quota`
- `POST /card/quota/add` — 新增
- `POST /card/quota/update` — 修改
- `POST /card/quota/page` — 分页

#### BankCardStockQuantityController — 卡库存管理 `/biz/cardStock`
- `POST /biz/cardStock/page` — 分页
- `POST /biz/cardStock/save` — 新增
- `GET /biz/cardStock/getStockByCardTitle/{platformType}/{cardTitle}` — 通过卡头获取卡库存
- `POST /biz/cardStock/adjustStockToApi` — Tevau调整库存至API
- `POST /biz/cardStock/adjustStockToApiQuery` — Tevau调整库存至API查询
- `POST /biz/cardStock/adjustStockFromApi` — API调整库存至Tevau
- `POST /biz/cardStock/adjustStockFromApiQuery` — API调整库存至TevauQuery

#### CardFreezeHistoryController — 冻结历史管理 `/cardFreezeHistory`
- `POST /cardFreezeHistory/page` — 分页查询冻结历史

#### BankCardFailureLogsController — 开卡失败记录 `/biz/bankCardFailureLog`
- `POST /biz/bankCardFailureLog/page` — 分页

#### PhysicalCardRecordsController — 三方卡号管理 `/biz/physicalCard`
- `POST /biz/physicalCard/page` — 分页
- `POST /biz/physicalCard/batchSave` — 新增
- `POST /biz/physicalCard/importEasyEurExcel` — 导入EasyEur文件
- `POST /biz/physicalCard/saveSxCardRecord` — (无描述)

#### TevaupayAuthCallbackController — 3DS记录 `/biz/tevaupayAuthCallback`
- `POST /biz/tevaupayAuthCallback/page` — 分页

#### CardInactiveRepaymentOrderController — 不活跃卡 `/biz/inactiveCardRepayment`
- `POST /biz/inactiveCardRepayment/page` — 分页
- `GET /biz/inactiveCardRepayment/export` — 导出

---

### 3.4 卡物流

#### BankCardLogisticsController — 物流信息管理 `/biz/cardLogistics`
- `POST /biz/cardLogistics/page` — 分页
- `GET /biz/cardLogistics/getDetail/{id}` — 详情
- `POST /biz/cardLogistics/updateLogisticsInfo` — 修改信息
- `POST /biz/cardLogistics/updateStatus` — 修改状态
- `GET /biz/cardLogistics/detailOfUpdateStatus/{logisticsId}` — 修改状态详情
- `POST /biz/cardLogistics/confirmCard` — 确认卡号
- `GET /biz/cardLogistics/detailOfConfirmCardNo/{logisticsId}` — 确认卡号详情
- `GET /biz/cardLogistics/export` — 导出

#### BankCardLogisticsBatchOperationController — 物流信息管理（批量）`/biz/cardLogistics`
- `GET /biz/cardLogistics/downloadConfirmCardTemplate` — 下载【批量确认卡号】模板
- `POST /biz/cardLogistics/importConfirmCard` — 批量确认卡号
- `GET /biz/cardLogistics/downloadShipperInfoTemplate` — 下载【批量修改物流发货信息信息】模板
- `POST /biz/cardLogistics/importShipperInfo` — 批量修改物流发货信息
- `GET /biz/cardLogistics/downloadUpdateStatusTemplate` — 下载【批量修改状态】模板
- `POST /biz/cardLogistics/importUpdateStatus` — 批量修改状态

---

### 3.5 交易与退款

#### CardRechargeRecordsController — 交易模块 `/biz/trans/records`
- `POST /biz/trans/records/toUpPage` — 分页卡充值记录列表
- `POST /biz/trans/records/tradePage` — 分页卡交易记录列表
- `GET /biz/trans/records/toUpRecordsExport` — 订单充值记录导出 exportType=1
- `GET /biz/trans/records/tradeRecordsExport` — 订单卡交易记录导出 exportType=2
- `GET /biz/trans/records/toUpBillRecordsExport` — 账单充值记录导出 exportType=3
- `GET /biz/trans/records/tradeBillRecordsExport` — 账单卡交易记录导出 exportType=4

#### CardTransactionRecordController — 卡交易记录 `/card/record`
- `POST /card/record/list` — 分页

#### OrderRefundController — 交易订单退款模块 `/biz/trans/refund`
- `POST /biz/trans/refund/listPage` — 分页
- `GET /biz/trans/refund/listPageExport` — 导出待退款交易核查
- `POST /biz/trans/refund/transChecklistPage` — 核查交易分页
- `POST /biz/trans/refund/transCheckOrder` — 交易核查相同金额订单
- `GET /biz/trans/refund/updateRefundStatus` — 修改退款订单状态
- `GET /biz/trans/refund/updateRefundRemark` — 修改退款订单备注
- `GET /biz/trans/refund/sendRefund` — 发起退款
- `POST /biz/trans/refund/allRefund` — 一键退款
- `POST /biz/trans/refund/allRefundAmount` — 一键退款金额统计

#### TransRefundController — 交易退款（无类级前缀、无 @ApiOperation）
- `POST /trans/reap/refund/page` — (无描述)
- `POST /trans/reap/refund` — (无描述)
- `POST /trans/reap/refund/fee` — (无描述)
- `POST /trans/reap/refund/refuse` — (无描述)
- `POST /trans/reap/refund/remark` — (无描述)
- `POST /trans/reap/refund/details` — (无描述)
- `GET /trans/reap/refund/page/export` — (无描述)

#### TransExceptionController — 交易异常（无类级前缀、无 @ApiOperation）
- `POST /trans/exception/page` — (无描述)
- `GET /trans/exception/page/export` — (无描述)

#### TransLogController — 交易日志（无类级前缀、无 @ApiOperation）
- `POST /trans/reap/log/page` — (无描述)
- `POST /trans/reap/log/details` — (无描述)
- `GET /trans/reap/log/page/export` — (无描述)

#### AdviceRefundController — Advice数据退款 `/trans/adviceRefund`
- `POST /trans/adviceRefund/page` — 退款日志分页(可传platType区分平台)
- `POST /trans/adviceRefund/detail` — 退款日志详情
- `POST /trans/adviceRefund/reap/query` — [Reap]按三方订单号查询待退款数据
- `POST /trans/adviceRefund/reap/refund` — [Reap]执行退款补偿
- `POST /trans/adviceRefund/sx/query` — [SX]按关联订单号查询待退款明细
- `POST /trans/adviceRefund/sx/refund` — [SX]执行退款补偿

#### CardBalanceAdjustRecordController — 调账 `/biz/cardBalanceAdjustRecord`
- `POST /biz/cardBalanceAdjustRecord/adjustAmount` — 调账
- `POST /biz/cardBalanceAdjustRecord/queryForPage` — 调账记录列表

#### SxRawDataLogController — SX原始回调日志 `/trans/sxRawDataLog`
- `POST /trans/sxRawDataLog/page` — 原始回调日志分页
- `POST /trans/sxRawDataLog/detail` — 原始回调日志详情(请求体 {"id": 123})

#### DataCardTradeController — 卡片交易数据 `/cardTrade/report`
- `POST /cardTrade/report/list` — 分页
- `GET /cardTrade/report/export` — 导出

#### DataCustTradeController — 客户交易数据 `/custTrade/report`
- `POST /custTrade/report/list` — 分页
- `GET /custTrade/report/export` — 导出

---

### 3.6 业务订单 / 风控审核

#### BusinessOrderController — 交易订单管理 `/biz/business/order`
- `POST /biz/business/order/depositPage` — 分页查询客户充币记录
- `POST /biz/business/order/withdrawPage` — 分页查询客户提币记录
- `POST /biz/business/order/transferPage` — 分页客户转账记录
- `POST /biz/business/order/updateAuditStatus` — 审核订单
- `GET /biz/business/order/depositOrderExport` — 充币导出 businessType=1
- `GET /biz/business/order/withdrawOrderExport` — 提币导出 businessType=2
- `GET /biz/business/order/transferOrderExport` — 转账导出 businessType=3
- `GET /biz/business/order/withdrawBillExport` — 客户提币账单导出 businessType=4

#### BusinessOrderAuditController — 订单审核设置管理 `/biz/business/order/audit`
- `POST /biz/business/order/audit/list` — 分页
- `POST /biz/business/order/audit/save` — 新增
- `POST /biz/business/order/audit/update` — 修改
- `POST /biz/business/order/audit/auditDepositOrder` — 充币风控审核
- `POST /biz/business/order/audit/auditWithdrawOrder` — 提币放行审核

#### RestrictConfigController — 黑白名单配置 `/biz/restrictConfig`
- `POST /biz/restrictConfig/page` — 分页查询黑白名单
- `POST /biz/restrictConfig/addMembers` — 批量添加黑白名单
- `POST /biz/restrictConfig/removeMembers` — 批量移除黑白名单
- `GET /biz/restrictConfig/refreshCache` — 刷新黑白名单缓存
- `POST /biz/restrictConfig/removeMemberById` — 按记录ID移除黑白名单（用于用户已注销但记录仍存在的场景）

---

### 3.7 KYC 审核

#### UserKycAuditRecordController — 用户kyc认证审核记录 `/biz/userKycAuditRecord`
- `POST /biz/userKycAuditRecord/page` — 分页
- `GET /biz/userKycAuditRecord/getDetail/{id}` — 获取详情
- `POST /biz/userKycAuditRecord/audit` — 审核

#### KycAuditConfigController — kyc审核配置 `/biz/kycAuditConfig`
- `GET /biz/kycAuditConfig/list` — 列表
- `POST /biz/kycAuditConfig/update` — 审核配置修改
- `POST /biz/kycAuditConfig/save` — 新增

#### FiatUSDKycReviewController — 法币USD_KYC审核管理 `/fiat/kyc`
- `POST /fiat/kyc/page` — KYC申请分页查询
- `GET /fiat/kyc/detail/{applicationNo}` — KYC申请详情
- `POST /fiat/kyc/review` — KYC审核操作

---

### 3.8 法币（Fiat USD）

#### FiatOrderController — 法币 `/fiat/order`
- `POST /fiat/order/rechargePage` — 客户法币充值记录查询
- `GET /fiat/order/rechargeExport` — 客户法币充值记录导出
- `POST /fiat/order/recharge/details` — (无描述)
- `POST /fiat/order/withdrawPage` — 客户法币提现记录查询
- `GET /fiat/order/withdrawExport` — 客户法币提现记录导出

#### FiatConversionController — 钱包兑换（无类级前缀）
- `POST /fiat/order/fiatConversionPage` — 客户币种兑换记录查询
- `GET /fiat/order/fiatConversionExport` — 客户币种兑换记录导出
- `POST /fiat/order/supplement` — (无描述)

#### FiatUSDRefundController — 法币USD提现退款管理 `/fiat/refund`
- `POST /fiat/refund/page` — 退款任务分页查询
- `GET /fiat/refund/detail/{taskId}` — 退款任务详情
- `POST /fiat/refund/execute` — 执行退款

#### FiatUsdRfiController — 法币RFI管理 `/fiat/rfi`
- `POST /fiat/rfi/page` — RFI分页查询
- `POST /fiat/rfi/detail` — RFI详情查询
- `POST /fiat/rfi/submit` — 提交RFI到上游

#### FiatLimitController — 法币限额（无类级前缀、无 @ApiOperation）
- `POST /fiat/limit/page` — (无描述)
- `POST /fiat/limit/detailById` — (无描述)
- `POST /fiat/limit/saveOrUpdate` — (无描述)

---

### 3.9 账单 / 财务对账

#### BillController — 账单管理 `/biz/bill/record`
- `POST /biz/bill/record/user` — 客户钱包账户变动记录
- `POST /biz/bill/record/platform` — 平台账户钱包变动记录
- `POST /biz/bill/record/despoit` — 充值
- `POST /biz/bill/record/withdraw` — 提现
- `GET /biz/bill/record/userRecordExport` — 客户钱包账户变动记录导出
- `GET /biz/bill/record/platformRecordExport` — 平台账户钱包变动记录导出

#### EeBillController — 账单管理（EE）`/biz/bill/record`
- `POST /biz/bill/record/queryForEeMainAccountPage` — EE主账户明细列表
- `GET /biz/bill/record/exportEeMainAccountDetail` — 导出EE主账户明细
- `POST /biz/bill/record/queryForEeFrozenAccount` — EE冻结账户明细列表
- `GET /biz/bill/record/exportEeFrozenAccountDetail` — 导出EE冻结账户明细
- `POST /biz/bill/record/queryForEeCardBilling` — EE卡账单列表
- `GET /biz/bill/record/exportEeCardBilling` — 导出EE卡账单列表

#### ReapBillController — 账单管理（Reap）`/biz/bill/record`
- `POST /biz/bill/record/queryForReapBilling` — Reap账单列表
- `GET /biz/bill/record/exportReapBilling` — 导出Reap账单列表

#### CardBillController — 账单管理（卡）`/bill`
- `POST /bill/userCardChangePage` — 客户卡变动记录分页
- `POST /bill/openCardPage` — 开卡分页
- `POST /bill/cancelCardPage` — 销卡分页
- `POST /bill/openCardRecordPage` — 开卡记录分页
- `POST /bill/cancelCardRecordPage` — 销卡记录分页
- `POST /bill/inTransitPage` — 在途资金账单分页
- `GET /bill/userCardChangeExport` — 客户卡帐户变动记录导出
- `GET /bill/inTransitExport` — 在途资金账单导出
- `GET /bill/openCardExport` — 开卡导出
- `GET /bill/cancelCardExport` — 销卡导出
- `GET /bill/openCardRecordExport` — 开卡记录导出
- `GET /bill/cancelCardRecordExport` — 销卡记录导出

#### SXCardBillController — SX账单管理 `/bill/sx/`
- `POST /bill/sx/sxCardAccountChangePage` — sx卡变动记录分页
- `GET /bill/sx/sxCardAccountChangeExport` — sx卡帐户变动记录导出

#### AccountRecordController — 账户变动记录统计 `/biz/finance/account`
- `POST /biz/finance/account/collectPage` — 归集记录查询
- `POST /biz/finance/account/withdrawPage` — 提币记录查询
- `POST /biz/finance/account/multiplePage` — 多签记录查询
- `POST /biz/finance/account/cardSellPage` — 卡销售收款查询
- `POST /biz/finance/account/partnerRecords` — 合作渠道方查询
- `POST /biz/finance/account/unCollect` — 未归集数据
- `POST /biz/finance/account/feePage` — 手续费账户数据查询
- `POST /biz/finance/account/userPage` — 用户账户数据查询
- `POST /biz/finance/account/platform` — 客户链上钱包地址查询
- `GET /biz/finance/account/exportPartner` — 导出
- `GET /biz/finance/account/exportCollect` — 导出
- `GET /biz/finance/account/exportWithdraw` — 导出
- `GET /biz/finance/account/exportMultiple` — 导出
- `GET /biz/finance/account/exportCardSell` — 导出
- `GET /biz/finance/account/exportUnCollect` — 导出
- `GET /biz/finance/account/exportFee` — 导出
- `GET /biz/finance/account/exportUser` — 导出
- `GET /biz/finance/account/exportPlatform` — 导出
- `GET /biz/finance/account/getBalance` — 查询余额

#### CardConsumeBillController — 卡消费账单 `/biz/finance/cardAccount`
- `POST /biz/finance/cardAccount/eePage` — ee列表查询
- `POST /biz/finance/cardAccount/reapPage` — reap列表查询
- `GET /biz/finance/cardAccount/reapExport` — reap导出
- `GET /biz/finance/cardAccount/eeExport` — ee导出

#### CardAccountOfflineRecordController — 主账户变动记录 `/biz/finance/cardAccount`
- `POST /biz/finance/cardAccount/list` — 分页
- `POST /biz/finance/cardAccount/save` — 保存
- `GET /biz/finance/cardAccount/delete` — 删除
- `GET /biz/finance/cardAccount/export` — 导出

#### AccountOfflineController — 线下钱包变动记录 `/biz/finance/offline`
- `POST /biz/finance/offline/page` — 列表查询
- `POST /biz/finance/offline/queryAddress` — 列表查询
- `POST /biz/finance/offline/save` — 新增
- `GET /biz/finance/offline/export` — 导出
- `POST /biz/finance/offline/import` — 导入

#### DataOfflineAdjustmentRecordController — 线下记账 `/biz/finance/adjustment`
- `POST /biz/finance/adjustment/page` — 列表查询
- `POST /biz/finance/adjustment/save` — 新增
- `DELETE /biz/finance/adjustment/delete/{id}` — 删除
- `GET /biz/finance/adjustment/export` — 导出
- `POST /biz/finance/adjustment/import` — 导入

#### DataLegalTenderBankController — 法币银行 `/biz/finance/tenderBank`
- `POST /biz/finance/tenderBank/page` — 列表查询
- `POST /biz/finance/tenderBank/update` — 修改

#### DataLegalTenderRecordController — 法币明细记录 `/biz/finance/tenderRecord`
- `POST /biz/finance/tenderRecord/saveData` — 新增
- `DELETE /biz/finance/tenderRecord/delete/{id}` — 删除
- `GET /biz/finance/tenderRecord/queryByCode` — 查询子项目
- `POST /biz/finance/tenderRecord/page` — 列表查询
- `GET /biz/finance/tenderRecord/export` — 导出，下载导出模板type传2，导出数据type传1
- `POST /biz/finance/tenderRecord/import` — 导入

#### FinanceWhitelistController — 证券白名单管理 `/biz/finance/whitelist`
- `POST /biz/finance/whitelist/page` — 分页查询
- `GET /biz/finance/whitelist/template` — 下载导入模板
- `POST /biz/finance/whitelist/import` — 批量导入
- `DELETE /biz/finance/whitelist/delete/{id}` — 删除

#### DataIncomeReportController — 收入报表 `/biz/finance/income`
- `POST /biz/finance/income/page` — 列表查询
- `GET /biz/finance/income/export` — 导出

#### DataOutflowReportController — 支出报表 `/biz/finance/outflow`
- `POST /biz/finance/outflow/page` — 列表查询
- `GET /biz/finance/outflow/export` — 导出

#### DataDailyTotalController — 财务汇总日表 `/biz/finance/total`
- `POST /biz/finance/total/page` — 列表查询
- `GET /biz/finance/total/export` — 导出

#### DataFinancePlatformController — 平台资金汇总 `/biz/finance/platformData`
- `POST /biz/finance/platformData/page` — 列表查询
- `GET /biz/finance/platformData/export` — 导出

#### AccountOtherController — 其他零散链上账户 `/biz/finance/otherAccount`
- `POST /biz/finance/otherAccount/page` — 列表查询
- `DELETE /biz/finance/otherAccount/delete/{id}` — 删除
- `POST /biz/finance/otherAccount/save` — 保存
- `GET /biz/finance/otherAccount/export` — 导出

#### AccountPlatformController — 平台账户管理 `/biz/account/platFrom`
- `POST /biz/account/platFrom/page` — 平台账户管理分页

#### AccountDailyInfoController — 结算管理 `/biz/account/daily/info`
- `POST /biz/account/daily/info/page` — 每日账户信息分页
- `POST /biz/account/daily/info/save` — 新增

#### AccountChannelController — 渠道账户管理 `/biz/accountChannel`
- `POST /biz/accountChannel/page` — 分页
- `POST /biz/accountChannel/save` — 新增
- `POST /biz/accountChannel/update` — 修改
- `DELETE /biz/accountChannel/delete/{accountId}` — 删除

---

### 3.10 费用配置

#### TransactionFeeConfigController — 交易手续费 `/biz/transactionFeeConfig`
- `POST /biz/transactionFeeConfig/page` — 分页
- `GET /biz/transactionFeeConfig/getDetail/{configId}` — 获取详情
- `POST /biz/transactionFeeConfig/save` — 新增
- `POST /biz/transactionFeeConfig/update` — 修改
- `DELETE /biz/transactionFeeConfig/delete/{configId}` — 删除
- `GET /biz/transactionFeeConfig/refreshCardChargeItemCache` — 刷新卡相关的手续费缓存

#### ChannelFeeConfigController — 渠道手续费 `/biz/channelFeeConfig`
- `POST /biz/channelFeeConfig/page` — 分页
- `GET /biz/channelFeeConfig/getDetail/{configId}` — 详情
- `POST /biz/channelFeeConfig/save` — 新增
- `POST /biz/channelFeeConfig/update` — 修改
- `DELETE /biz/channelFeeConfig/delete/{configId}` — 删除
- `GET /biz/channelFeeConfig/refreshCache` — 刷新渠道手续费缓存

#### MonthlyFeeController — 月费管理 `/biz/monthly`
- `POST /biz/monthly/page` — 月费管理分页
- `GET /biz/monthly/export` — 导出

#### MonthlyFeeDetailsController — 月费详情管理 `/biz/monthly/details`
- `POST /biz/monthly/details/page` — 月费详情分页
- `GET /biz/monthly/details/export` — 导出

#### PlatformRechargeExchangeRateController — 卡方充值汇率管理 `/biz/exchangeRate`
- `POST /biz/exchangeRate/page` — 分页
- `GET /biz/exchangeRate/getPlatformRate` — 获取平台对应汇率
- `GET /biz/exchangeRate/refreshCache/{platformType}`、`GET /biz/exchangeRate/refreshCache` — 刷新平台汇率的缓存
- `POST /biz/exchangeRate/save` — 新增
- `POST /biz/exchangeRate/calcAfterRechargeRate` — 计算充值后汇率

---

### 3.11 营销活动

#### ActivityController — 活动数据 `/activity/`
- `GET /activity/znqDataExport` — 周年庆活动数据导出
- `POST /activity/importZNQRanking` — 导入排行榜排行榜数据
- `POST /activity/importInvitaRanking` — 导入排行榜排行榜数据-推荐总人数
- `GET /activity/initWeight` — 初始化周年庆奖品权重
- `POST /activity/reapSxPage` — 活动奖励金流水分页
- `GET /activity/reapSxExport` — 活动奖励金流水导出
- `POST /activity/sxIssuerRecordPage` — sx账单分页
- `GET /activity/sxIssuerRecordExport` — sx账单导出
- `POST /activity/sxBillingHistoryDetailsPage` — SX客户卡交易明细分页
- `GET /activity/sxBillingHistoryDetailsExport` — SX客户卡交易明细导出
- `POST /activity/sxTransExceptionPage` — SX交易异常查询分页
- `GET /activity/sxTransExceptionExport` — SX交易异常查询导出

#### ActivityPeriodsController — 活动期数管理 `/activity`
- `GET /activity/typeList` — 活动类型列表（activityType + activityTypeName）
- `POST /activity/list` — 活动列表（不分页）
- `POST /activity/save` — 新增活动
- `POST /activity/update` — 修改活动
- `POST /activity/periods/page` — 期数分页列表（含状态标签）
- `POST /activity/periods/save` — 新增期数
- `POST /activity/periods/update` — 修改期数
- `POST /activity/periods/delete` — 删除期数

#### ActivityRankingController — 活动榜单管理 `/activity/ranking`
- `POST /activity/ranking/list` — 榜单列表（不分页，全量）
- `POST /activity/ranking/save` — 新增榜单记录
- `POST /activity/ranking/update` — 修改榜单记录
- `POST /activity/ranking/delete` — 删除榜单记录（逻辑删除）

#### ActivityAccountRechargeController — 活动账户手动充值 `/activity/accountRecharge`
- `POST /activity/accountRecharge/recharge` — 执行单次充值
- `POST /activity/accountRecharge/page` — 充值日志分页
- `GET /activity/accountRecharge/activityOptions` — 活动下拉选项
- `POST /activity/accountRecharge/rechargeByActivity` — 按活动批量充值(自动对 Reap + SX 两个账户都充)

#### ActivityChrisBlacklistController — 活动黑名单管理 `/activity/blacklist`
- `POST /activity/blacklist/list` — 黑名单列表（不分页）
- `POST /activity/blacklist/save` — 新增黑名单
- `POST /activity/blacklist/update` — 修改黑名单
- `POST /activity/blacklist/delete` — 删除黑名单（逻辑删除）

#### ZnqRewardController — ZNQ排行榜发奖 `/activity/znqReward`
- `POST /activity/znqReward/lookup` — 按邀请码查用户(发放前核对)
- `POST /activity/znqReward/send` — 单条发放排行榜奖励
- `GET /activity/znqReward/activityOptions` — 活动类型下拉选项
- `POST /activity/znqReward/page` — 发奖日志分页

#### VoucherController — 代金券 `voucher/user`
- `POST voucher/user/page` — 分页
- `POST voucher/user/importUser` — 导入
- `GET voucher/user/exportVoucher` — 代金券导出
- `POST voucher/user/importPage` — 代金券导入分页
- `POST voucher/user/sendVoucher` — 发送代金券

#### DiscountCodeConfigController — 折扣码配置 `/biz/discountCodeConfig`
- `POST /biz/discountCodeConfig/page` — 分页
- `GET /biz/discountCodeConfig/getDetail/{configId}` — 获取详情
- `POST /biz/discountCodeConfig/save` — 新增
- `POST /biz/discountCodeConfig/update` — 修改

#### DiscountCodeUsageController — 折扣码使用记录 `/biz/discountCodeUsage`
- `POST /biz/discountCodeUsage/page` — 分页
- `GET /biz/discountCodeUsage/export` — 导出

---

### 3.12 积分系统（points）

#### PointsDashboardController — 积分-数据看板 `/biz/points/dashboard`
- `GET /biz/points/dashboard/overview` — 看板概览

#### PointsPrizeConfigController — 积分-兑换配置 `/biz/points/prizeConfig`
- `POST /biz/points/prizeConfig/page` — 分页查询
- `POST /biz/points/prizeConfig/save` — 新增兑换配置
- `POST /biz/points/prizeConfig/update` — 修改兑换配置
- `GET /biz/points/prizeConfig/info/{id}` — 详情

#### PremiumBoxConfigController — 积分-高级盒配置 `/biz/points/premiumBox`
- `GET /biz/points/premiumBox/info` — 获取高级盒配置
- `POST /biz/points/premiumBox/update` — 修改高级盒配置

#### PointsAntiBrushConfigController — 积分-防刷配置 `/biz/points/antiBrush`
- `GET /biz/points/antiBrush/info` — 获取防刷配置
- `POST /biz/points/antiBrush/update` — 修改防刷配置

#### PointsCodeController — 积分-Code管理 `/biz/points/code`
- `POST /biz/points/code/page` — 分页查询
- `POST /biz/points/code/create` — 创建Code
- `POST /biz/points/code/batchCreate` — 批量创建Code
- `POST /biz/points/code/disable/{id}` — 停用Code
- `GET /biz/points/code/info/{id}` — 详情
- `POST /biz/points/code/usages/{codeId}` — 查询Code使用记录
- `GET /biz/points/code/export` — 导出Excel

#### PointsCodeUsageController — 积分-Code使用记录 `/biz/points/codeUsage`
- `POST /biz/points/codeUsage/page` — 分页查询
- `GET /biz/points/codeUsage/export` — 导出Excel

#### PrizeRuleController — 积分-概率规则配置 `/biz/points/rule`
- `POST /biz/points/rule/range/page` — 金额区间-分页
- `POST /biz/points/rule/range/save` — 金额区间-新增
- `POST /biz/points/rule/range/update` — 金额区间-修改
- `POST /biz/points/rule/range/delete/{id}` — 金额区间-删除
- `POST /biz/points/rule/item/page` — 奖品档位-分页
- `POST /biz/points/rule/item/save` — 奖品档位-新增
- `POST /biz/points/rule/item/update` — 奖品档位-修改
- `POST /biz/points/rule/item/delete/{id}` — 奖品档位-删除

#### PointsBalanceController — 积分-用户余额查询 `/biz/points/balance`
- `POST /biz/points/balance/page` — 分页查询
- `GET /biz/points/balance/export` — 导出Excel

#### PointsTransactionController — 积分-积分明细 `/biz/points/transaction`
- `POST /biz/points/transaction/page` — 分页查询
- `GET /biz/points/transaction/export` — 导出Excel

#### PointsRedemptionController — 积分-兑换记录 `/biz/points/redemption`
- `POST /biz/points/redemption/page` — 分页查询
- `GET /biz/points/redemption/export` — 导出Excel

#### PointsOperationLogController — 积分-操作日志 `/biz/points/operationLog`
- `POST /biz/points/operationLog/page` — 分页查询
- `GET /biz/points/operationLog/export` — 导出Excel

#### PointsLarkAlertConfigController — 积分-飞书预警配置 `/biz/points/larkAlert`
- `POST /biz/points/larkAlert/page` — 分页查询
- `POST /biz/points/larkAlert/save` — 新增预警配置
- `POST /biz/points/larkAlert/update` — 修改预警配置
- `POST /biz/points/larkAlert/delete/{id}` — 删除预警配置

#### PointsBlacklistController — 积分-黑名单管理 `/biz/points/blacklist`
- `POST /biz/points/blacklist/page` — 分页查询
- `POST /biz/points/blacklist/save` — 新增黑名单
- `POST /biz/points/blacklist/delete/{id}` — 移除黑名单
- `GET /biz/points/blacklist/export` — 导出Excel

#### PointsLuckyBoxController — 积分-盒子查询 `/biz/points/luckyBox`
- `POST /biz/points/luckyBox/page` — 分页查询
- `GET /biz/points/luckyBox/info/{id}` — 详情
- `GET /biz/points/luckyBox/export` — 导出Excel

#### PointsTaskController — 积分-子任务管理 `/biz/points/task`
- `POST /biz/points/task/page` — 分页查询
- `POST /biz/points/task/save` — 新增
- `POST /biz/points/task/update` — 修改
- `GET /biz/points/task/info/{id}` — 详情

#### PointsPoolController — 积分-积分池管理 `/biz/points/pool`
- `POST /biz/points/pool/page` — 分页查询
- `POST /biz/points/pool/save` — 新增积分池
- `POST /biz/points/pool/update` — 调整积分池
- `GET /biz/points/pool/info/{id}` — 详情

---

### 3.13 返佣

#### RebateConfigController — 返佣配置管理 `/biz/rebateConfig`
- `POST /biz/rebateConfig/page` — 分页
- `POST /biz/rebateConfig/save` — 新增
- `POST /biz/rebateConfig/update` — 修改
- `GET /biz/rebateConfig/queryRebateInvitationLevel` — 邀请等级查询

#### RebateRecordController — 返佣记录 `/biz/rebateRecord`
- `POST /biz/rebateRecord/page` — 分页
- `GET /biz/rebateRecord/export` — 导出

#### RebateDailyReportController — 客户返佣日报-统计报表 `/biz/rebateDailyReport`
- `POST /biz/rebateDailyReport/page` — 分页
- `GET /biz/rebateDailyReport/export` — 导出

#### RebateCommDailySumController — 返佣日报汇总-统计报表 `/biz/rebateCommDailySum`
- `POST /biz/rebateCommDailySum/page` — 分页
- `GET /biz/rebateCommDailySum/export` — 导出

---

### 3.14 理财（financing）

#### FinancingProductController — 理财产品 `biz/financing/product`
- `POST biz/financing/product/page` — 分页
- `POST biz/financing/product/updateById` — 修改产品

#### FinancingProductI18nController — 理财产品国际化 `biz/financing/product/i18n`
- `GET biz/financing/product/i18n/listAllByProductId/{productId}` — 查询产品国际化列表
- `POST biz/financing/product/i18n/updateById` — 更新产品文案

#### FinancingPlatformProductManagerController — 平台产品管理 `biz/financing/platformProductManager`
- `POST biz/financing/platformProductManager/page` — 分页
- `GET biz/financing/platformProductManager/export` — 导出

#### FinancingPlatformProductDetailController — 平台产品明细 `biz/financing/platformProductDetail`
- `POST biz/financing/platformProductDetail/page` — 分页
- `GET biz/financing/platformProductDetail/export` — 导出

#### FinancingPlatformProfitDetailController — 平台收益明细 `biz/financing/platformProfitDetail`
- `POST biz/financing/platformProfitDetail/page` — 分页
- `GET biz/financing/platformProfitDetail/export` — 导出

#### FinancingUserOrderDetailController — 理财账户流水明细 `biz/financing/userOrderDetail`
- `POST biz/financing/userOrderDetail/page` — 理财账户流水明细列表
- `GET biz/financing/userOrderDetail/export` — 理财账户流水明细导出

#### FinancingUserProfitDetailController — 用户收益明细 `biz/financing/userProfitDetail`
- `POST biz/financing/userProfitDetail/page` — 分页
- `GET biz/financing/userProfitDetail/export` — 导出

#### FinancingUserProductAccountController — 客户理财产品分布 `biz/financing/userProductAccount`
- `POST biz/financing/userProductAccount/page` — 客户当前理财产品分布列表
- `GET biz/financing/userProductAccount/export` — 客户当前理财产品分布列表-导出

#### FinancingRevenueRuleController — 收益分配规则 `biz/financing/revenueRule`
- `POST biz/financing/revenueRule/page` — 分页
- `POST biz/financing/revenueRule/updateById` — 修改收益分配规则

#### FinancingReportController — 理财日报 `biz/financing/report`
- `POST biz/financing/report/page` — 理财日报分页
- `GET biz/financing/report/export` — 理财日报导出

---

### 3.15 商城（mall）

#### MallProductController — wot商城商品 `biz/mallProduct`
- `POST biz/mallProduct/page` — 分页
- `POST biz/mallProduct/save` — 新增
- `GET biz/mallProduct/getDetail/{productId}` — 详情
- `POST biz/mallProduct/update` — 修改
- `POST biz/mallProduct/removeByIds` — 批量删除
- `POST biz/mallProduct/updateStatus` — 修改状态
- `GET biz/mallProduct/getTypeList` — 获取商品类型列表
- `GET biz/mallProduct/refreshCache/{productId}` — 刷新商品缓存

#### MallOrderManagementController — 商城订单管理 `/mall/order`
- `POST /mall/order/page` — 分页查询
- `GET /mall/order/exportMallOrder` — 导出商城订单列表
- `POST /mall/order/confirmPay` — 确认付款

#### MallCardSubOrderController — 商城卡子订单管理 `/mall/card/sub`
- `POST /mall/card/sub/page` — 分页查询
- `GET /mall/card/sub/exportCardSubOrder` — 导出商城卡子订单
- `GET /mall/card/sub/detail` — 详情查询
- `POST /mall/card/sub/importSerialNumber` — 导入上传的卡序号
- `POST /mall/card/sub/shipping` — 发货
- `GET /mall/card/sub/cardIdList` — 查询卡列表

#### MallNoncardSubOrderController — 商城非卡子订单管理 `/mall/nonCard/sub`
- `POST /mall/nonCard/sub/page` — 分页查询
- `GET /mall/nonCard/sub/exportNonCardSubOrder` — 导出商城非卡子订单
- `GET /mall/nonCard/sub/detail` — 详情查询
- `POST /mall/nonCard/sub/importNonCardId` — 导入上传的发货商品id
- `POST /mall/nonCard/sub/shipping` — 发货
- `GET /mall/nonCard/sub/nonCardIdList` — 查询商品列表

---

### 3.16 任务系统（task）

#### TaskConfigController — 任务配置管理 `/biz/taskConfig`
- `POST /biz/taskConfig/page` — 分页查询
- `GET /biz/taskConfig/detail/{id}` — 查询详情
- `POST /biz/taskConfig/save` — 新增
- `POST /biz/taskConfig/update` — 修改
- `POST /biz/taskConfig/delete/{id}` — 删除
- `POST /biz/taskConfig/changeStatus` — 启用/禁用

#### TaskConfigLanController — 任务配置多语言管理 `/biz/taskConfigLan`
- `GET /biz/taskConfigLan/list/{taskId}` — 查询任务的多语言列表
- `POST /biz/taskConfigLan/save` — 新增多语言
- `POST /biz/taskConfigLan/update` — 修改多语言
- `POST /biz/taskConfigLan/delete/{id}` — 删除多语言

#### TaskUserRecordController — 用户任务记录管理 `/biz/taskUserRecord`
- `POST /biz/taskUserRecord/page` — 分页查询
- `GET /biz/taskUserRecord/stats/{taskId}` — 任务统计概览
- `POST /biz/taskUserRecord/export` — 导出用户任务记录

#### TaskExcelListController — 任务Excel名单管理 `/biz/taskExcelList`
- `POST /biz/taskExcelList/page` — 分页查询
- `POST /biz/taskExcelList/import` — 导入Excel名单
- `POST /biz/taskExcelList/deleteByTaskId/{taskId}` — 按任务ID删除名单
- `POST /biz/taskExcelList/deleteByBatchNo/{batchNo}` — 按批次号删除名单
- `POST /biz/taskExcelList/delete` — 按ID删除名单
- `POST /biz/taskExcelList/add` — 手动追加单个客户
- `GET /biz/taskExcelList/template` — 下载Excel导入模板

#### DailyTaskCompletionLogController — 日常任务完成记录管理 `/biz/dailyTaskCompletionLog`
- `POST /biz/dailyTaskCompletionLog/page` — 分页查询

---

### 3.17 消息中心

#### MsgController — 消息中心模板管理 `/msg/manage`
- `POST /msg/manage/page` — 消息分页
- `GET /msg/manage/getDetail/{msgId}` — 消息-详情
- `POST /msg/manage/save` — 新增
- `POST /msg/manage/update` — 修改
- `DELETE /msg/manage/delete/{msgId}` — 删除
- `POST /msg/manage/saveOrUpdateMsgDetails` — 修改或者保存消息详情

#### MsgEmailTempController — 消息邮件模板管理 `/biz/msg/email`
- `POST /biz/msg/email/page` — 消息邮件模板分页
- `GET /biz/msg/email/getDetail/{id}` — 消息邮件模板-详情
- `POST /biz/msg/email/save` — 新增
- `POST /biz/msg/email/update` — 修改
- `DELETE /biz/msg/email/delete/{id}` — 删除

#### MsgEmailTempAdminController — 管理后台消息邮件模板管理 `/biz/msg/batchPush`
- `POST /biz/msg/batchPush/save` — 新增
- `POST /biz/msg/batchPush/page` — 管理后台消息邮件模板分页
- `GET /biz/msg/batchPush/getDetail/{id}` — 管理后台消息邮件模板-详情
- `POST /biz/msg/batchPush/update` — 修改
- `POST /biz/msg/batchPush/push` — 推送
- `POST /biz/msg/batchPush/excel` — 推送
- `POST /biz/msg/batchPush/job` — 推送
- `POST /biz/msg/batchPush/pushRecordPage` — 管理后台消息邮件推送记录
- `POST /biz/msg/batchPush/pushDetail` — 管理后台消息邮件推送记录详情
- `GET /biz/msg/batchPush/downMsgTem` — 下载批量推出导入模板

---

### 3.18 内容运营

#### BlogManageController — Blog管理 `/biz/blog`
- `POST /biz/blog/save` — 保存
- `POST /biz/blog/listByPage` — 列表查询
- `GET /biz/blog/detail` — 详情查询
- `GET /biz/blog/tokenOff` — 下架
- `GET /biz/blog/addView` — 添加浏览数
- `GET /biz/blog/addShare` — 添加分享数
- `GET /biz/blog/addLike` — 添加点赞数
- `GET /biz/blog/carouselList` — 轮询图列表
- `POST /biz/blog/blogPage` — 分页查询首页
- `GET /biz/blog/blogDetail` — 首页详情信息

#### WebsiteVerificationController — Blog管理（官网校验）`/biz/blog`
- `GET /biz/blog/verification` — 官网tg和email校验

#### BannerConfigController — banner配置 `/biz/bannerConfig`
- `POST /biz/bannerConfig/page` — 分页
- `POST /biz/bannerConfig/save` — 新增
- `POST /biz/bannerConfig/update` — 修改
- `GET /biz/bannerConfig/refreshCache` — 刷新banner缓存

#### ExplorePageAdminController — 探索页管理 `/explore/page`
- `POST /explore/page/list` — 分页查询探索页列表
- `GET /explore/page/detail/{id}` — 查询探索页详情（含图片列表）
- `POST /explore/page/add` — 新增探索页
- `POST /explore/page/update` — 编辑探索页
- `POST /explore/page/delete` — 逻辑删除探索页
- `GET /explore/page/getExploreInfo` — 查询自定义探索页预览
- `POST /explore/page/refreshCache` — 刷新探索页列表缓存

#### FunctionEntryController — 功能区入口管理 `/biz/function/entry`
- `POST /biz/function/entry/list` — 查询全部入口列表（下拉）
- `POST /biz/function/entry/page` — 分页查询功能区入口列表
- `POST /biz/function/entry/detail` — 查询功能区入口详情
- `POST /biz/function/entry/save` — 新增功能区入口
- `POST /biz/function/entry/update` — 修改功能区入口
- `POST /biz/function/entry/delete` — 删除功能区入口

#### FunctionCategoryController — 功能区分类管理 `/biz/function/category`
- `POST /biz/function/category/list` — 查询全部启用分类列表（下拉）

#### FunctionI18nController — 功能区多语言管理 `/biz/function/i18n`
- `POST /biz/function/i18n/page` — 分页查询功能区多语言配置列表
- `POST /biz/function/i18n/save` — 新增功能区多语言配置
- `POST /biz/function/i18n/update` — 修改功能区多语言配置
- `POST /biz/function/i18n/delete` — 删除功能区多语言配置
- `POST /biz/function/i18n/listByBiz` — 查询业务对象全部多语言配置
- `POST /biz/function/i18n/batchSave` — 批量保存多语言配置

---

### 3.19 文件

#### FileRecordController — 文件记录 `/biz/fileRecord`
- `POST /biz/fileRecord/uploadForUrl` — 上传文件信息，返回地址

---

### 3.20 第三方对接

#### ReapController — reap接口 `/biz/reapApi`
- `GET /biz/reapApi/reapCreationScript` — reap脚本
- `GET /biz/reapApi/getPhysicalCardShippingOrderByBulkShipId` — 通过发货id，获取实体卡订单信息

#### BinanceOrderController — 币安订单管理 `/biz/binance/order`
- `POST /biz/binance/order/customerPage` — 币安主账户订单明细查询
- `POST /biz/binance/order/merchantDataReport` — 币安主账户统计查询
- `GET /biz/binance/order/userExport` — 导出

---

### 3.21 国家地区

#### CountryAreaController — 国家地区 `/sys/countryArea`
- `GET /sys/countryArea/getList/{lan}` — 国家地区列表

---

### 3.22 系统日志 / 定时任务 / 运营日报

#### SysLogOperationController — 操作日志 `sys/log/operation`
- `GET sys/log/operation/page` — 分页
- `GET sys/log/operation/export` — 导出

#### SysLogErrorController — 异常日志 `sys/log/error`
- `GET sys/log/error/page` — 分页
- `GET sys/log/error/export` — 导出

#### SysLogLoginController — 登录日志 `sys/log/login`
- `GET sys/log/login/page` — 分页
- `GET sys/log/login/export` — 导出

#### TevaupayLogOperationController — Tevau 操作日志（无类级前缀、无 @Api）
- `POST /biz/tevaupay/logOperationPage` — (无描述)

#### ScheduleJobController — 定时任务 `/sys/schedule`
- `GET /sys/schedule/page` — 分页
- `GET /sys/schedule/{id}` — 信息
- `POST /sys/schedule` — 保存
- `PUT /sys/schedule` — 修改
- `DELETE /sys/schedule` — 删除
- `PUT /sys/schedule/run` — 立即执行
- `PUT /sys/schedule/pause` — 暂停
- `PUT /sys/schedule/resume` — 恢复

#### ScheduleJobLogController — 定时任务日志 `/sys/scheduleLog`
- `GET /sys/scheduleLog/page` — 分页
- `GET /sys/scheduleLog/{id}` — 信息

#### DataDailyReportController — 运营日报 `/daily/report`
- `POST /daily/report/list` — 分页
- `GET /daily/report/export` — 导出

---

## 4. 对「客服 AI 系统」最有价值的部分

后台已经沉淀了大量客服/工单/风控所需的现成能力，AI 客服系统可直接复用或对齐这些接口（多数最终通过 Feign 调用下游服务执行真正的写操作）。重点如下：

### 4.1 用户查询与处置（客服日常最高频）
- **客户信息查询**：`TevaupayUserController` — 分页查询、`getDetail/{id}` 详情、用户编号下拉。用户状态/标签/邀请关系处置：`updateStatus`、`updateTag`、`updateInvitationLevel`、`signOff/{id}`（注销）、`clearGaInfo`（清谷歌验证器，处理 2FA 锁死场景）。
- **用户层级关系**：`UserScriptController.queryUserHierarchy`（上下级链路，处理邀请/返佣纠纷）。
- **登录与设备**：`UserLoginRecordController`（注册登录 IP）、`ThirdLoginController`（三方账号查询/解绑）、`SysLogLoginController`（后台登录日志）。
- **收货地址 / 三方认证**：`BankUserReceiveAddressController`、`UserCertificationRecordController`。

### 4.2 卡相关处置（客服核心场景：卡被锁/冻结/丢失/换 PIN）
- **卡查询**：`UserBankCardController` — 分页、详情、`getBalance/{id}`、`getCardConfiguration`、`getCardNumber3dsDetail`、`getTokenList`。
- **卡锁定/解锁/状态**：`UserBankCardController.unlock/{id}`（解锁卡）、`updateCardStatus`（修改状态）、`cancelCard`（注销卡）、`resetCardPin`（重置 PIN）、`updateCardConfiguration`、`updateCardTokenStatus`。
- **冻结历史**：`CardFreezeHistoryController.page`（查冻结历史，对应下游 `accountFreezeOperate` 人工冻结/解冻）。
- **开卡失败排查**：`BankCardFailureLogsController.page`。
- **限额**：`CardQuotaConfigController`。
- **物流（实体卡寄送进度）**：`BankCardLogisticsController`（详情、修改状态、确认卡号、导出）。
- 对应下游 Feign：`CardMgmtBankCardUserFeign`（冻结卡 / 注销卡 / 解锁卡 / 重置 PIN / 改卡状态等）。

### 4.3 交易查询与退款（客服处理「钱没到/扣错/要退款」）
- **交易/充值记录**：`CardRechargeRecordsController`（充值记录、卡交易记录分页+导出）、`CardTransactionRecordController.list`、`DataCardTradeController` / `DataCustTradeController`（交易数据报表）。
- **退款处理**：`OrderRefundController`（核查交易、发起退款 `sendRefund`、一键退款 `allRefund`、改退款状态/备注）、`AdviceRefundController`（Reap/SX 按订单号查询待退款并执行补偿）、`TransRefundController`（reap 退款流程）。
- **调账**：`CardBalanceAdjustRecordController.adjustAmount`（人工调账）+ 调账记录列表。
- **异常交易**：`TransExceptionController`、`SxRawDataLogController`（原始回调日志，排查到账问题）。
- 对应下游 Feign：`TransRefundFeign`（订单退款/多次退款）、`TransFeign`（查卡余额/单笔交易）。

### 4.4 KYC 审核（工单类审核流程，可对齐 AI 辅助审核）
- `UserKycAuditRecordController` — KYC 审核记录分页、`getDetail/{id}` 详情、`audit` 审核（通过/驳回）。
- `KycAuditConfigController` — KYC 审核配置。
- `UserKycController.page` — KYC 操作日志。
- 法币 KYC：`FiatUSDKycReviewController`（申请分页、详情、`review` 审核）。
- 下游：`UserFeign.updateUserKycAuditRecord`、`getKycLevel2LivingImage`（活体图片）。

### 4.5 充提币 / 转账风控审核（工单 + 风控）
- `BusinessOrderController` — 客户充币/提币/转账记录查询 + `updateAuditStatus` 审核。
- `BusinessOrderAuditController` — `auditDepositOrder`（充币风控审核）、`auditWithdrawOrder`（提币放行审核）+ 审核规则配置。
- `RestrictConfigController` — 黑白名单（批量增删、刷新缓存），客服/风控拉黑或放行。
- `ActivityChrisBlacklistController`、`PointsBlacklistController` — 活动/积分维度黑名单。

### 4.6 账单与对账（客服解释「这笔扣费是什么」）
- `BillController`（客户钱包变动、充值、提现）、`CardBillController`（开卡/销卡/卡变动/在途资金）、`EeBillController` / `ReapBillController` / `SXCardBillController`（各卡方账单）。
- 财务侧 `finance.*` 全套报表用于深度对账（收入/支出/汇总/平台资金/手续费/归集提币）。

### 4.7 消息触达（客服主动通知用户）
- `MsgEmailTempAdminController`（批量邮件推送 push/excel/job + 推送记录）、`MsgController` / `MsgEmailTempController`（模板管理）。
- 下游：`UserFeign.sendShippingNoticeEmail`、`sendJiguangNotice`（极光推送）、`kickOutByUserId`（强制下线）。

### 4.8 营销补偿（客服安抚/补偿用户）
- `VoucherController.sendVoucher`（发代金券）、`ActivityAccountRechargeController`（活动账户充值）、积分 `PointsPoolController` / `PointsPrizeConfigController`。

### 客服 AI 复用建议（要点）
1. **只读查询类**（用户/卡/交易/账单/KYC/物流的 page、detail、getBalance、记录查询）可直接被 AI 客服编排为「查询工具」，安全风险低，优先接入。
2. **写/处置类**（解锁卡、重置 PIN、改状态、注销卡、审核、退款、调账、拉黑、强制下线、发券）应作为 AI 的「受控动作」，需走人工确认或权限校验——这些动作背后多为 Feign 调下游，且后台已有操作日志（`SysLogOperationController`/`TevaupayLogOperationController`）可审计。
3. **工单流程**目前以「KYC 审核 + 充提币审核 + 黑白名单」三类审核为主，没有独立的「客服工单」Controller——AI 客服若要做工单系统，需新建，但可对齐这三套审核的状态机与审计模式。
