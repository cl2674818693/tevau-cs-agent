# TevauPay-Service 接口地图（C 端 APP 后端）

## 1. 服务概述

TevauPay-Service 是 Tevau **C 端 APP 后端**，服务于终端持卡用户的 APP。系统是基于 Spring Cloud 的微服务，按业务域拆分为多个子模块（tevaupay-user / card / wallet / trans / account / business-order / mall / marketing / financing / fiat / external / data-statistics 以及证券投资 tevaufinance-investment 等）。

鉴权：APP 端请求经 `tevaupay-gateway` 网关统一处理，采用 **Sa-Token + Redis** 做登录态管理；`loginId == userId == t_tevaupay_user.id`（用户主键）。绝大多数 `controller`（非 feign/rpc/task）属于 APP 对外接口，需登录态；带 `feignController` / `rpc` / `Rpc` / `task` / `scheduled` 的是服务间内部调用（Feign/MQ/定时任务），不直接对 APP 暴露。

文档说明：
- 路径 = 类级 `@RequestMapping` 前缀 + 方法级 `@XxxMapping` 路径（原文如何写就如何拼，未规整前导斜杠）。
- 功能描述优先取 `@ApiOperation` 中文原文；无则取方法路径并标注「(无描述)」。
- 同一 controller 内出现多个相同路径（如多个 `getCurrentUserInfo`/`getCurrencyBalanceList`）是**多版本接口**（按 APP 版本灰度路由，如 V10003/V10012/V11000/V11008/V11030/V11038/V11009），均如实列出。
- 本文以 APP 对外 controller 为主线全量收录；feign/rpc/job/api 内部契约接口在各模块末尾按 controller 收录类名与代表路径（这类接口不对 APP 暴露，故不逐一展开全部方法）。

---

## 2. tevaupay-user 用户模块

### UserController — 用户信息（@Api 用户信息）
- POST `user/login` — 登录（多版本，3 个 login）
- POST `user/login` — 登录
- POST `user/applePayLogin` — 登录（Apple 登录）
- POST `user/register` — 注册
- POST `user/saveOrUpdateUserDeviceInfo` — 新增或修改设备 id
- POST `user/loginOut` — 退出登录
- POST `user/switchDeviceLanguage` — 切换语言
- POST `user/getCurrentUserInfo` — 获取当前登录用户信息（多版本，3 个）
- POST `user/updateBindEmail` — 修改绑定邮箱
- POST `user/setPassword` — 设置密码
- POST `user/setPhone` — 设置手机号
- GET `user/getPhoneInfo` — 获取设置手机号信息
- GET `user/getIpAndLocation` — 获取 ip 地址信息
- POST `user/getEmailExistsStatus` — 获取邮箱是否存在
- GET `user/parseExternalToken` — 解析三方 token 信息
- POST `user/getLoginEmail` — 获取用户登录邮箱
- POST `user/updateNickName` — 更新用户昵称
- GET `user/queryByEmailOrInviteCode` — 根据邮箱或邀请码查询用户信息（返回邮箱、昵称和邀请码），查询不到返回空

### UserV11000Controller — 用户信息（@Api 用户信息）
- POST `user/register` — 注册
- POST `user/resetPassword` — 重置密码

### UserV11009Controller — 用户信息（@Api 用户信息）
- POST `user/register` — 注册
- POST `user/login` — 登录（多版本，2 个）

### UserKycController — 用户 kyc 信息（@Api 用户kyc信息）
- POST `user/userKyc/saveKycInfo` — kyc 认证
- GET `user/userKyc/getKycInfo` — 获取 kyc 认证信息
- POST `user/userKyc/getKycUrl` — 获取 KYC 链接地址
- POST `user/userKyc/getLevel2Result` — 获取 KYC 二级验证结果
- POST `user/userKyc/getKycCertificationProcess` — 开卡获取 kyc 认证流程
- (RequestMapping) `user/userKyc/saveKycAllInfo` — 保存 kyc 所有信息不对接前端，API 绿色通道，指定 IP 可访问

### OldlUserKycController — 用户 kyc 信息（@Api 用户kyc信息，老版本）
- POST `user/userKyc/saveKycInfo` — kyc 认证
- GET `user/userKyc/getKycInfo` — 获取 kyc 认证信息
- POST `user/userKyc/getKycUrl` — 获取 KYC 链接地址
- POST `user/userKyc/getLevel2Result` — 获取 KYC 二级验证结果
- POST `user/userKyc/getKycCertificationProcess` — 开卡获取 kyc 认证流程

### JumIoController — 用户 kyc 信息（@Api 用户kyc信息，JumIo 回调）
- (RequestMapping) `user/userKyc/notifyKyc` — kyc 结果回调
- (RequestMapping) `user/userKyc/updateUserLevel` — (无描述)

### BalanceController — 余额模块（@Api 余额模块）
- POST `user/balance/options` — 获取余额下拉选项列表
- POST `user/balance/detail` — 获取余额详情（余额+功能入口）

### FunctionEntryController — 功能入口（@Api 功能入口）
- POST `user/function/home-entries` — 获取首页功能区入口列表
- POST `user/function/more-entries` — 获取多功能页面入口列表

### PaymentCodeController — 支付密码（@Api 支付密码）
- POST `user/paymentCode/bind` — 设置支付密码
- POST `user/paymentCode/forgetPaymentCode` — 忘记支付密码
- POST `user/paymentCode/updatePaymentCode` — 修改支付密码

### PaymentCodeV11000Controller — 支付密码（@Api 支付密码）
- POST `user/paymentCode/bind` — 设置支付密码
- POST `user/paymentCode/bindBeyondSetting` — 设置之外绑定支付密码
- POST `user/paymentCode/forgetPaymentCode` — 忘记支付密码
- POST `user/paymentCode/updatePaymentCode` — 修改支付密码
- POST `user/paymentCode/validate` — 校验支付密码

### GoogleAuthenticatorController — 谷歌验证码（@Api 谷歌验证码）
- GET `user/ga/generateGoogleToken` — 生成谷歌验证码
- POST `user/ga/bindGoogleToken` — 绑定谷歌验证码
- POST `user/ga/updateSettingStatus` — 用户开启关闭谷歌验证
- POST `user/ga/updateGoogleToken` — 修改谷歌验证器 token

### UserSettingController — 用户设置（@Api 用户设置）
- GET `/user/userSetting/getSettingStatus` — 获取支付密码、谷歌验证码状态（多版本，2 个）

### UserPreferenceController — 用户偏好（@Api 用户偏好）
- POST `user/preference/save` — 保存用户偏好

### TransactionDetailSettingController — 交易详情（@Api 交易详情）
- POST `user/transactionDetailSetting/updateStatus` — 用户开启关闭交易详情

### EmailController — 邮件信息（@Api 邮件信息）
- POST `user/email/getValidateCodes` — 获取验证码
- POST `user/email/getValidateCode` — 获取验证码（多版本，3 个 getValidateCode/getValidateCodes）
- POST `user/email/validateEmailCode` — 验证邮箱验证码是否正确
- GET `user/email/getEmailConfig` — 获取邮箱配置信息

### ThirdLoginController — 用户三方登录（@Api 用户三方登录）
- GET `user/third/getLoginOptions` — 获取三方登录列表
- POST `user/third/authenticateWithBoundToken` — Token 绑定认证（判断是否绑定 Tevau 账号、是否首次登录）
- POST `user/third/firstTimeBindingLogin` — 首次登录
- POST `user/third/enrollMfaCredential` — 多因素认证绑定（解除老绑定并以三方认证账号绑定登录）
- GET `user/third/resultThirdList` — 返回三方登录列表
- POST `user/third/bindThirdPartyAccount` — 绑定三方登录账号
- POST `user/third/api/line/login` — 绑定三方登录账号（Line 登录）
- POST `user/third/getIpDetail` — 绑定三方登录账号（取 IP 详情）
- POST `user/third/getThirdBindEmail` — 查询当前邮箱是否绑定过当前需要登录的三方平台

### MsgCenterController — 消息中心（@Api 消息中心）
- POST `user/msg/selectAll` — 分页查询
- POST `user/msg/allRead` — 消息全部已读
- GET `user/msg/singleRead` — 消息单个已读
- GET `user/msg/details` — 查看消息详情
- POST `user/msg/msgNoReadTotal` — 查询用户未读消息总和

### TaskController — 任务中心（@Api 任务中心）
- POST `user/task/assign` — (无描述)
- POST `user/task/list` — 查询任务列表（按类型筛选，含状态统计）
- POST `user/task/home` — 查询首页任务列表
- POST `user/task/markNode` — 点击完成任务（completionType=14，幂等）

### UserGuidanceController — 用户引导（@Api 用户引导）
- POST `user/guide/skip` — 跳过进度
- GET `user/guide/progress` — 查询用户引导进度

### BannerController — banner 信息（@Api banner信息）
- GET `user/banner/query` — 查询 banner 图
- GET `user/banner/popUp` — 查询弹窗图
- GET `user/banner/getBanner` — 根据类型查询 banner 图
- GET `user/banner/three/query` — 查询三方 banner 图
- GET `user/banner/three/popUp` — 查询三方弹窗图
- GET `user/banner/initRestrictConfigData` — 初始化黑白名单数据

### FAQController — FAQ 管理中心（@Api FAQ管理中心）
- POST `user/getFAQ` — 获取 FAQ 链接

### UserFeedbackController — 用户反馈（@Api 用户反馈）
- POST `user/feedback/save` — 保存用户反馈

### FileRecordController — 文件上传（@Api 文件上传）
- POST `user/file/uploadFileInfo` — 上传文件信息
- GET `user/file/previewImage` — 获取文件地址

### CountryAreaController — 国家地区信息（@Api 国家地区信息）
- (RequestMapping) `user/countryArea/getCountryArea` — 获取国家地区（多版本，多个 getCountryArea）
- (RequestMapping) `user/countryArea/flushCountryArea` — 刷新国家缓存信息
- (RequestMapping) `user/countryArea/getCountryAreaByWeb` — 获取国家地区

### CountryAreaPhoneController — 国家地区信息（@Api 国家地区信息）
- (RequestMapping) `user/countryAreaPhone/getCountryAreaPhoneInfo` — (无描述)
- (RequestMapping) `user/countryAreaPhone/getCountryAreaPhoneInfoByWeb` — (无描述)

### CurrencyController — 货币（无 @Api 描述）
- GET `user/countryCurrency/flushCountryCurrency` — (无描述)
- GET `user/countryCurrency/getCountryCurrencyInfo` — (无描述)

### DictTypeController — 获取字典信息（@Api 获取字典信息）
- POST `user/dict/getDictDataByWeb` — 获取数据字典（多版本，多个）
- POST `user/dict/getDictData` — 获取数据字典（多版本，多个）

### MallUserController — 商城用户信息（@Api 商城用户信息）
- POST `/user/mall/register` — 注册
- POST `/user/mall/login` — 登录
- POST `/user/mall/loginOut` — 退出登录

### UserExternalOperationController — 外部用户信息（@Api 外部用户信息）
- POST `user/external/setCommunicationInfo` — 设置用户手机号和邮箱

### UpdateVersionController — 用户信息（@Api 用户信息）
- POST `user/version/updateVersion` — 升级版本
- POST `user/version/ip2regionSearcher` — (无描述)

### InternalController — 邮件信息（@Api 邮件信息）
- GET `user/add/account` — 添加账户
- GET `user/add/email` — 添加账户

### AlibabaCaptchaController — 国家地区信息（@Api，实际为滑动验证）
- POST `user/validate/captcha` — 滑动验证
- POST `user/validate/enableCaptcha` — 滑动验证

### JiguangNoticeController — 极光推送回调通知（@Api 极光推送回调通知）
- (RequestMapping) `user/notice/notifyMsg` — 消息回调通知
- GET `user/notice/sendTextNotice` — (无描述)

### InvestmentGlobalSwitchController — 证券全局开关（@Api 证券全局开关）
- GET `/user/investmentData/switch/global` — 获取证券全局开关状态

### GrayUserConfigController — 灰度接口配置（@Api 灰度接口配置）
- GET `user/gray/config/getApi` — (无描述)

### UserInvitationRecordController — 用户邀请记录（无 @Api 描述）
- 类内无独立 @XxxMapping 提取行 — (无描述)

### UserNewInvitationRecordController — 新邀请记录
- GET `/user/userNewInvitationRecord/initUserNewInvitationRecord` — 初始化邀请层级关系
- POST `/user/userNewInvitationRecord/updateUserNewInvitationRecord` — 修改邀请层级关系

### 内部/Feign/定时（不对 APP 暴露）
- UserInnerController（implements UserFeign, UserFeignTask，`user/...`，含 getPaymentCode、scheduled/* 定时）
- UserExternalController（`/external/user`，implements UserExternalFeign）
- UserKycFeignContoller（`external/kyc`）
- UserDownStreamFeignController（`user/downStream`）
- UserNewInvitationRecordFeignController（`/user/userNewInvitationRecord`）
- UserPreferenceInternalController（`user/preference`，getDepositPreference/deleteDepositPreference/markDepositPreferenceDeposited）
- TaskInternalController（`user/task/internal`，implements TaskProcessFeign）
- FileRecordFeignController（`user/file/getOpenCardFileReport`）
- PaymentCodeFeignController（`user/paymentCode/validatePaymentCode`）
- GoogleCodeFeignController（`user/ga`，validateGaCode/getGoogleTokenStatus）
- CountryAreaFeignController（`user/countryArea`）、CountryCurrencyFeignController（`user/countryCurrency`）
- MsgCenterFeignController（`user/msgCenter`）、SmsFeignController（`user/sms`）、DictFeignController（`user/dictInfo`）、EmailFeignController（`user/emailInfo`）
- BannerFeignController（`/banner`）、RestrictConfigFeignController（`/restrictConfig`）、UserRocketMqFeignController（`user/mq`）

---

## 3. tevaupay-card 银行卡模块

### BankCardUserController — 银行卡用户（无 @Api 描述，类级 `card/bankCardUser`）
- POST `card/bankCardUser/getCustBankcard` — 获取客户银行卡信息
- GET `card/bankCardUser/getCustBankcardDetail` — 获取客户银行卡信息详情
- POST `card/bankCardUser/verifyWalletBalance` — 校验钱包余额是否大于等于开卡费用
- POST `card/bankCardUser/getCvvInfo` — 获取 cvv 信息
- POST `card/bankCardUser/updateCardStatusByInner` — 修改卡信息
- POST `card/bankCardUser/getBestNewCardType` — 获取最新的开卡类型
- POST `card/bankCardUser/createWallet` — 创建钱包
- POST `card/bankCardUser/getCardTempInfoByCardNum` — 根据卡号获取卡模板信息
- POST `card/bankCardUser/getCardStatusById` — 根据卡 id 获取添加卡片状态
- POST `card/bankCardUser/bindCardInfo` — 绑定客户银行卡信息
- POST `card/bankCardUser/getHandlingfee` — 获取手续费
- POST `card/bankCardUser/updateCardAliasName` — 卡添加别名
- POST `card/bankCardUser/activeCard` — 激活实体卡接口
- POST `card/bankCardUser/lockCard` — 锁卡并解锁卡信息
- POST `card/bankCardUser/cancelCard` — 注销卡
- POST `card/bankCardUser/setDefaultCard` — 设置默认卡
- POST `card/bankCardUser/getApplicationRecord` — 获取申请卡记录
- POST `card/bankCardUser/saveUserAddress` — 添加卡保存居住地址
- POST `card/bankCardUser/getCardHomePageInfo` — 获取卡首页信息
- POST `card/bankCardUser/getCardDetail` — 获取卡详情（不传 id 则返回默认卡）

### BankCardUserV10003Controller — 银行卡用户 V10003（`card/bankCardUser`）
- POST `card/bankCardUser/getCvvInfo` — 获取 cvv 信息
- POST `card/bankCardUser/createBankcard` — 创建客户银行卡信息
- POST `card/bankCardUser/rechargeCreditCard` — 卡充值
- POST `card/bankCardUser/lockCard` — 锁卡并解锁卡信息
- POST `card/bankCardUser/cancelCard` — 注销卡
- POST `card/bankCardUser/bindCardInfo` — 绑定客户银行卡信息

### BankCardUserV10012Controller — 银行卡用户 V10012（`card/bankCardUser`）
- POST `card/bankCardUser/getCvvInfo` — 获取 cvv 信息
- POST `card/bankCardUser/createBankcard` — 创建客户银行卡信息
- POST `card/bankCardUser/rechargeCreditCard` — 卡充值
- POST `card/bankCardUser/lockCard` — 锁卡并解锁卡信息
- POST `card/bankCardUser/cancelCard` — 注销卡
- POST `card/bankCardUser/bindCardInfo` — 绑定客户银行卡信息

### BankCardUserV11000Controller — 银行卡信息改版接口（@Api 银行卡信息改版接口，`card/bankCardUser`）
- POST `card/bankCardUser/getCustBankcard` — 获取客户银行卡信息
- POST `card/bankCardUser/getBestNewCardType` — 获取最新的开卡类型
- POST `card/bankCardUser/updateCardPin` — 修改卡 pin 信息
- POST `card/bankCardUser/getCardDetailInfoById` — 获取详细状态信息、物流
- POST `card/bankCardUser/getPreOenCardInfo` — 获取预开卡信息
- POST `card/bankCardUser/createBankcard` — 创建客户银行卡信息
- POST `card/bankCardUser/verifyWalletBalance` — 校验钱包余额是否大于等于开卡费用
- GET `card/bankCardUser/getCardStatusAndWalletStatus` — 获取申请卡状态和钱包状态（多版本，2 个）
- POST `card/bankCardUser/getCvvInfo` — 获取 cvv 信息
- POST `card/bankCardUser/cancelCard` — 注销卡
- POST `card/bankCardUser/lockCard` — 锁卡并解锁卡信息
- POST `card/bankCardUser/getApplicationRecord` — 获取申请卡记录

### BankCardUserV11008Controller — 银行卡信息支持 Bitware 币种（@Api 银行卡信息支持Bitware币种，`card/bankCardUser`）
- POST `card/bankCardUser/getPreOenCardInfo` — 获取预开卡信息（多版本，2 个）
- POST `card/bankCardUser/createBankcard` — 创建客户银行卡信息
- POST `card/bankCardUser/rechargeCreditCard` — 卡充值
- GET `card/bankCardUser/getCustBankcardDetail` — 获取客户银行卡信息详情
- POST `card/bankCardUser/getHandlingfee` — 获取手续费
- POST `card/bankCardUser/getUserPrepareRechargeWallet` — 获取预充值

### BankCardUserV11030Controller — 银行卡用户 V11030（`card/bankCardUser`）
- POST `card/bankCardUser/cardOpeningCompensation` — (无描述)
- GET `card/bankCardUser/getCustBankcardDetail` — 获取客户银行卡信息详情

### BankCardUserV11038Controller — 银行卡用户接口 V1.1.038（@Api 银行卡用户接口 V1.1.038，`card/bankCardUser`）
- POST `card/bankCardUser/activeCard` — 激活实体卡 - id 和 activeCode 必传，通过卡 id 直接定位

### ApplePayController — Apple Pay（`card/bankCardUser`）
- POST `card/bankCardUser/payNotify` — 支付回调
- POST `card/bankCardUser/applePayInAppProvisionings` — 获取应用内配置信息
- POST `card/bankCardUser/applePayInAppProvisioning` — 获取应用内配置信息
- POST `card/bankCardUser/getUserHolderBindCardInfo` — 获取用户绑卡信息
- POST `card/bankCardUser/saveUserHolderBindCardInfo` — 保存用户绑卡信息
- POST `card/bankCardUser/getButtonStatus` — 获取按钮状态（多版本，2 个）
- POST `card/bankCardUser/checkAllCardBindAppleDevices` — 检测卡用户名下卡的状态
- POST `card/bankCardUser/getTokenList` — 获取按钮状态
- GET `card/bankCardUser/getUserCards` — 获取用户卡信息

### ApplePayNotifyController — Apple Pay 回调（无类级前缀）
- POST `/card/bankCardUser/payNotifyApplePay` — 支付回调

### BankCardTransactionController — 银行卡交易（`card/bankCardTransaction`）
- POST `card/bankCardTransaction/getBankCardTransactionDetail` — 获取交易详情信息

### BankCardUserV10012 之外 — VoucherController — 用户代金券（@Api 用户代金券，`/card/voucher`）
- POST `/card/voucher/getUserVoucherPage` — 查询用户代金券列表

### DiscountCodeUsageController — 优惠码（@Api 优惠码，`card/discountCodeUsage`）
- POST `card/discountCodeUsage/getOpenCardDiscountFee` — 获取开卡折扣费用（多版本，2 个）

### BankCardReceiveAddressController — 银行卡收货地址（@Api 银行卡收货地址，`card/cardReceiveAddress`）
- POST `card/cardReceiveAddress/saveCardReceiveAddress` — 保存银行卡收货地址
- POST `card/cardReceiveAddress/getCardReceiveAddress` — 获取银行卡收货地址

### BankUserReceiveAddressController — 用户收获地址管理（@Api 用户收获地址管理，`card/useReceiveAddress`）
- POST `card/useReceiveAddress/saveReceiveAddress` — 保存收货地址
- POST `card/useReceiveAddress/updateReceiveAddress` — 修改收货地址
- POST `card/useReceiveAddress/getReceiveAddressList` — 获取收货地址列表
- POST `card/useReceiveAddress/deleteReceiveAddress` — 删除收获地址
- POST `card/useReceiveAddress/saveOrUpdateReceiveAddress` — 新增或修改收货地址

### BankCardBillAddressController — 银行卡账单地址（@Api 银行卡账单地址，`card`）
- GET `card/tempBillAddress/checkUserHasAddress` — 用户是否保存账单地址
- POST `card/tempBillAddress/saveOrUpdateTempBillAddress` — 保存或修改银行卡账单地址
- POST `card/tempBillAddress/getCardBillAddress` — 获取卡信息临时账单地址
- POST `card/billAddress/syncHistoryBillAddress` — 同步历史账单地址
- POST `card/billAddress/getBankCardUserBillAddress` — 获取银行卡账单地址

### BankCardLogisticsController — 银行卡物流（`card/bankCardLogistics`）
- POST `card/bankCardLogistics/getBankCardLogistics` — 获取银行卡物流信息

### BankCardTemplateController — 银行卡管理模板（@Api 银行卡管理模板，`card/bankCardChannel`）
- GET `card/bankCardChannel/getBankCardTemplateDetail` — 获取银行卡模板详细信息
- POST `card/bankCardChannel/getList` — 获取银行卡管理模板列表信息（多版本，多个 getList）

### BankCardCountryExtraFeeController — 银行卡对应国家额外信息表（@Api，`card/bankCardChannel`）
- GET `card/bankCardChannel/updateCardCountryExtraFee` — 修改国家额外费用信息

### CardConfigController — 获取银行卡配置信息（@Api 获取银行卡配置信息，`card/config`）
- POST `card/config/getCardConfigInfo` — 获取银行卡配置信息

### ThirdPartyController — h5 新增接口（@Api h5新增接口，`/card/thirdParty`）
- GET `/card/thirdParty/getAuthorizableAmount` — 获取授权金额

### StraitsxCardController — StraitsX Card Management（@Api StraitsX Card Management，`/card/straitsx`）
- (RequestMapping) `/card/straitsx/getPinSetupIframeUrl` — (无描述)
- (RequestMapping) `/card/straitsx/confirmCardPin` — (无描述)

### CardInactiveFeeDeductionController — 不活跃扣费（`card/cardInactiveFeeDeduction`）
- GET `card/cardInactiveFeeDeduction/syncBankCardInfoToInactiveChargingRecordTable` — 同步历史数据
- POST `card/cardInactiveFeeDeduction/handleInactiveBankCardRulesDataTask` — 执行不活跃规则

### CardScheduledController — 卡调度初始化（@Api 卡调度初始化，`/card/deduction/fee`）
- POST `/card/deduction/fee/initScheduled` — 初始化扣费调度卡
- POST `/card/deduction/fee/autoDeductionFee` — 进行月费扣费处理
- POST `/card/deduction/fee/scheduleOverdueMonthlyFeeDeductions` — 进行欠月费扣费处理

### DataCompensationController — 数据补偿（@Api 数据补偿，`card/compensation`）
- (RequestMapping) `card/compensation/compensationCardReward` — 补偿开卡开卡奖励
- (RequestMapping) `card/compensation/createBillEntriesForMaking` — 制作中补偿流水

### 内部/Feign/定时（不对 APP 暴露）
- BankCardUserFeignController（`/card/cardUser`，implements BankCardUserFeign + CardMgmtBankCardUserFeign；含 updateCardStatus、updateCardBalance、getBankCardUser、cardMgmtCardMake、autoRechargeToCard、accountFreezeOperate、freezeSingleCard、unfreezeCard、getFreezeHistory）
- BankCardUserTaskFeignTaskController（`/card/scheduled`，processExpiredFreezeRecords 等）
- CardMonthFeeTaskController（`card/month/fee`）、BankCardScheduledController（`/card/monthly/scheduled`）、BankCardScheduledDetailsController（`/card/monthly/details`）
- CardInactiveFeeDeductionFeignController（`card/cardInactiveFeeDeduction`）、BankCardFailureLogsFeignController（`/card/cardFailedCompensation`）
- BankCardStockFeignController（`card/stock`）、DiscountCodeTaskController（`/card/scheduled`）、DiscountCodeUsageFeignController（`/card/discount`）
- BankThirdPartyCardUserFeignController（`/card/scheduled`）、AddressValidationFeignController（`/card/addressValidation`）
- BankCardReceiveAddressFeignController（`card/cardReceiveAddress`）、BankCardTransactionTaskFeignTaskController（`/card/scheduled`）
- CompensationCardScheduleFeignController（`/card/compensationSchedule/scheduled`）、EEMoveOutFeignController（`/card/EEMoveOut`）
- BankCardTemplateFeignController（`card/bankCardChannel`）、CardVoucherFeignController（`/card/voucher`）、BankUserCardWalletFeignController（`card/wallet`）

---

## 4. tevaupay-wallet 钱包模块

### WalletController — 钱包相关（@Api 钱包相关，`/wallet`）
- GET `/wallet/getCommonData` — 钱包操作查询文案
- GET `/wallet/getTxResult` — 提币，转账结果查询
- GET `/wallet/getFee` — 查询手续费
- GET `/wallet/getCurrency` — 查询币种（多版本，2 个）
- GET `/wallet/getNetwork` — 查询币种网络
- GET `/wallet/getBalance` — 获取钱包余额
- GET `/wallet/getCurrentBalance` — 获取币种钱包余额
- GET `/wallet/getCurrencyBalance` — 获取钱包币种余额
- GET `/wallet/getCurrencyBalanceList` — 获取钱包币种余额集合（多版本：含 V039、字典控制排序版等共 6 个同路径）
- GET `/wallet/getAddress` — 获取账户地址
- POST `/wallet/withdraw` — 提现
- POST `/wallet/transfer` — 转账
- GET `/wallet/bitwaveTradeCheck` — 查询 bitwave 开关
- GET `/wallet/getBitwaveBalance` — 查询 bitwave 余额
- GET `/wallet/queryWalletCurrencyBalance` — 查询钱包币种余额
- GET `/wallet/usdToBalance` — usd 换算 btcw 余额
- GET `/wallet/getBalanceChart` — 查询余额变化曲线图
- GET `/wallet/getTotalAssets` — 查询钱包总资产
- GET `/wallet/getDepositMinAmount` — 查询最小充币金额

### WalletBinanceController — 钱包币安相关（@Api 钱包币安相关，`/wallet/binance`）
- GET `/wallet/binance/createBinanceOrder` — 创建币安订单
- POST `/wallet/binance/webhook` — webhook 通知
- GET `/wallet/binance/testCompensation` — 补偿测试
- GET `/wallet/binance/getAmountThreshold` — 获取充提币金额限制
- GET `/wallet/binance/getWithdrawTargetType` — 查询币安提币目标信息类型

### WatchAddressController — 钱包监控地址订阅管理（@Api 钱包监控地址订阅管理，`/wallet/watch-address`）
- POST `/wallet/watch-address/subscribe` — 订阅监控地址
- POST `/wallet/watch-address/update` — 修改订阅
- POST `/wallet/watch-address/list` — 查询订阅列表

### WalletCoreCallbackController — 钱包核心回调（`/wallet/callback`）
- POST `/wallet/callback/receive` — (无描述)

### AccountChannelController — 账户渠道（`/account-channel`）
- GET `/account-channel/list` — (无描述)
- GET `/account-channel/insert` — (无描述)
- GET `/account-channel/update` — (无描述)
- GET `/account-channel/delete` — (无描述)
- GET `/account-channel/detail` — (无描述)

### DataRetryController — 钱包数据补偿/重试（`/wallet/data/retry`，运维补偿类）
- GET `/wallet/data/retry/tronTrx` — 回收 trx - 旧路径
- GET `/wallet/data/retry/chainSync` — 回收 trx
- GET `/wallet/data/retry/retryUnCollectData` — 归集未处理数据 - 旧路径
- GET `/wallet/data/retry/collectProc` — 归集未处理数据
- GET `/wallet/data/retry/initAccount` — (无描述)
- GET `/wallet/data/retry/withdrawCompensation` — (无描述)
- GET `/wallet/data/retry/orderRepair` — (无描述)
- GET `/wallet/data/retry/addBloomValue` — 添加 bloomFilter 数据 - 旧路径
- GET `/wallet/data/retry/filterAdd` — 添加 bloomFilter 数据
- GET `/wallet/data/retry/redisBloomCheck` — 校验 bloomFilter 数据 - 旧路径
- GET `/wallet/data/retry/filterCheck` — 校验 bloomFilter 数据
- GET `/wallet/data/retry/setChannelValue` — 设置渠道账户余额 - 旧路径
- GET `/wallet/data/retry/cacheUpdate` — 设置渠道账户余额
- GET `/wallet/data/retry/orderMqMqRetry` — (无描述)
- GET `/wallet/data/retry/mqResend` — (无描述)
- GET `/wallet/data/retry/createAccount` — (无描述)
- GET `/wallet/data/retry/rebate` — (无描述)
- GET `/wallet/data/retry/chongzhi` — (无描述)
- GET `/wallet/data/retry/kaika` — (无描述)

### MockDepositController — 模拟充币回调（全部注释掉，无活跃接口）

### 内部/Feign/定时（不对 APP 暴露）
- ChainFeignRpc（`/wallet/chain`）、WalletScheduleFeignRpc（`/wallet/scheduled`）、WalletTransactionRpc（`/wallet/feign`）、WalletAccountFeignRpc（`/wallet/account`）

---

## 5. tevaupay-trans 交易模块（tevaupay-trans-app）

### TransController — 交易模块（@Api 交易模块，`/trans/records`）
- POST `/trans/records/page` — 分页列表
- GET `/trans/records/transactionDetails` — (无描述)
- GET `/trans/records/queryAccountBalance` — (无描述)
- GET `/trans/records/getSingleTransaction` — (无描述)

### TransV11000Controller — 交易模块（@Api 交易模块，`/trans/records`）
- POST `/trans/records/page` — 分页列表（多版本，3 个同路径）
- GET `/trans/records/transactionDetails` — (无描述)

### WalletTransController — 钱包交易模块（@Api 钱包交易模块，`/trans/wallet`）
- POST `/trans/wallet/page` — 分页列表

### CardBillStatisticsController — 卡账单统计（@Api 卡账单统计，`/trans/statistics`）
- POST `/trans/statistics/monthlyBilling` — 近 6 月卡账单数据
- POST `/trans/statistics/transSuccessRate` — 近 6 月交易成功率
- POST `/trans/statistics/merchantCountryDistribution` — 交易商户地区分布

### Card3dsAuthController — 3ds 操作（@Api 3ds操作，`/trans/auth`）
- POST `/trans/auth/auth` — (无描述)

### PaymentController — （无 @Api 描述，`/card`）
- GET `/card/listTrans` — (无描述)

### ReapRefundController — Reap 新订单退款（@Api Reap新订单退款，`/trans/refund`）
- GET `/trans/refund/newOrderRefund` — (无描述)
- GET `/trans/refund/orderMessage` — (无描述)

### TransCompensateEventController — 交易模块（@Api 交易模块，`/trans/event`）
- POST `/trans/event/createWalletRecordsEventCon` — 创建钱包记录事件
- POST `/trans/event/kycCompensateEventCon` — kyc 回调补偿
- POST `/trans/event/physicalCardRechargeEventCon` — 充值补偿
- POST `/trans/event/cardStatusCompensateEventCon` — 卡状态变更补偿

### PayChannelController — 国际化服务（@Api 国际化服务，`/pay/channel`）
- POST `/pay/channel/payChannel` — (无描述)

### BatchApplyVirtualCardController — 交易记录补偿服务（@Api 交易记录补偿服务，`/trans/batch/card`）
- POST `/trans/batch/card/batch` — (无描述)
- GET `/trans/batch/card/getCardPan` — (无描述)
- GET `/trans/batch/card/updateApplyCardPan` — (无描述)
- GET `/trans/batch/card/retrieveAllCardDesign` — (无描述)
- POST `/trans/batch/card/bulkShipPhysicalCards` — (无描述)
- POST `/trans/batch/card/physicalCardShippingByShipId` — (无描述)
- GET `/trans/batch/card/showCardPanHTML` — (无描述)
- GET `/trans/batch/card/showCardPanByCardId` — (无描述)

### ActivityRewardsRecordController — 交易记录补偿服务（@Api 交易记录补偿服务，`/trans/rewards`）
- POST `/trans/rewards/activityRewards` — (无描述)
- POST `/trans/rewards/stressActivityRewards` — (无描述)

### BlockPurseController — 交易记录补偿服务（@Api 交易记录补偿服务，`/card/vcc`）
- GET `/card/vcc/compensate` — (无描述)
- GET `/card/vcc/test` — (无描述)

### SXAdjustController — 手动调整脚本（@Api 手动调整脚本，`/sx/trans/adjust`）
- POST `/sx/trans/adjust/execute` — execute
- POST `/sx/trans/adjust/refundSettle` — refundSettle
- POST `/sx/trans/adjust/reimburse` — reimburse

### Test3dsController — 交易模块（@Api 交易模块，`/trans/3ds`）
- POST `/trans/3ds/json` — 分页列表

### I18nRefreshController — 国际化服务（@Api 国际化服务，`/trans/i18n`）
- GET `/trans/i18n/i18nRefresh` — (无描述)

### WebHookRegisterController — 国际化服务（@Api 国际化服务，`/trans/tools/`，运维工具类，路径众多）
- POST `/trans/tools/cacheWhiteCardIds`、POST `/register`、POST `/delete`、GET `/query`、POST `/sendCardRewards`、POST `/sendCardRewardsNew`、GET `/queryCtx`、GET `/initEEHistoricalTransactionData`、GET `/queryAccountEntry`、GET `/queryWallet`、GET `/cardPin`、GET `/accountAdjustment`、POST `/updateEEMasterAccount`、POST `/reap/register`、GET `/reap/updateReapPin`、GET `/reap/updateCurrentReapPin`、GET `/reap/initPreData`、GET `/reap/unblockCard`、POST `/ee/eeCardRecharge`、POST `/reap/reapCardRecharge`、GET `/reap/reapAccountInit`、GET `/reap/update3DSForwardingMethod`、GET `/reap/get3DSForwardingStatus`、GET `/queryCtxInfo`、GET `/reap/reapInitReward`、GET `/reap/reapInviteAccountInit`、GET `/reap/reapInviteAccountInitNew`、GET `/reap/snapshotInit`、GET `/eeSettled`、GET `/manualRecharge`、GET `/sxManualRecharge`、POST `/clearingSkyDaoCardCache` — 均(无描述)

### Webhook 回调（第三方支付渠道回调，非 APP 直连）
- ReapWebHookController（`/trans/reap/webHook`，@Api webhook事件回调：getSettlementReports、callback、callback1、timeOutTest）
- SXWebHookController（`/sx/trans`：auth StraitsX authorization 事件回调、webHook StraitsX Webhook 事件回调）
- EasyEuroWebHookController（`/trans/webHook/callback` easyeuro webhook 事件回调）
- VccWebhookController（`/trans/callback`：notify 交易内容通知、tradesCompensating）

### 内部/Feign/RPC（不对 APP 暴露，节选）
TransScheduledRpc、Card3dsAuthRpc、ReapWebHookCommandRpc、EasyEuroCardRecordsRpc、CardChannelRpc、CardRechargeRecordRpc、ActivityRewardsRecordRpc、FeeRpc、SXCardChannelRpc、TransRefundRpc、SXTransScheduledRpc、AsyncOpenCardRpc、ApplyPhysicalCardRpc、TransCompensateEventRpc、TransCardScheduledRpc、TransCardRechargeRecordsRpc、SXRefundScheduledRpc、AccountAdjustmentRpc、CardRecordsRpc、WalletTransactionRecordsRpc、ReapTransactionRpc。

---

## 6. tevaupay-account 卡账户模块（均为内部 RPC，不对 APP 暴露）

### AccountController — 交易记录补偿服务（@Api，`/cardaccount/account`）
- GET `/cardaccount/account/getAccount`、POST `/concurrentRecharge`、POST `/authorization`、GET `/processExpireData`、POST `/updateAccounting`、GET `/platformFeeUndo`、GET `/initRedisAccount`、POST `/platformCashDetail`、POST `/platformRewardCashDetail`、POST `/event`、POST `/eventReward`、POST `/settlementRefund`、GET `/platformCashCompensation`、POST `/refundCompensation`、GET `/activity/delay`、GET `/adjustAccountCache`、POST `/undoDetails` — 均(无描述)

### RPC：CardAccountingRpc（`/account`）、SXCardAccountingRpc（`/sxAccount`）、CardAccountActivityDetailsRpc（`/account/activity`）、CardRefundRpc（`/refund`）、CardTradeDetailRpc（`/details`）

---

## 7. tevaupay-business-order 钱包记录/订单模块

### BusinessOrderController — 订单-钱包记录（@Api 订单-钱包记录，`/order`）
- POST `/order/page` — 分页列表
- GET `/order/queryByOrderId` — 根据 orderId 查询
- GET `/order/walletDetails` — (无描述)
- GET `/order/idrPendingDetails` — (无描述)
- GET `/order/idrDetails` — (无描述)
- GET `/order/fiatDetails` — (无描述)

### 内部 RPC：BusinessOrderRpc（`/business-order`，@Api 订单服务）

---

## 8. tevaupay-mall 商城模块

### OrderManagementController — 订单管理（@Api 订单管理，`/mall/orderManagement`）
- POST `/mall/orderManagement/createOrder` — 创建订单信息
- POST `/mall/orderManagement/getOrderStatus` — 获取订单支付状态
- POST `/mall/orderManagement/confirmPaymentMethod` — 确认支付方式
- POST `/mall/orderManagement/getOrderQrcode` — 扫描二维码获取订单信息
- POST `/mall/orderManagement/getPendingOrderDetail` — 获取待支付订单详情
- POST `/mall/orderManagement/getUserOrders` — 获取用户订单
- POST `/mall/orderManagement/orderManagementNotifyByInner` — 订单管理回调
- POST `/mall/orderManagement/getOrderDetailByNumber` — 根据订单号获取订单详情

### MallProductController — 商城商品（@Api 商城商品，`/mall/product`）
- POST `/mall/product/detail` — 获取商品详情

### PaymentWayController — 订单支付方式（@Api 订单支付方式，`/mall/paymentWay`）
- POST `/mall/paymentWay/getPaymentWayList` — 获取支付方式集合

### AntomPayController — Antom 支付（@Api Antom支付，`/mall/antomPay`）
- POST `/mall/antomPay/createPaymentSession` — 创建付款会话(创建支付订单)
- POST `/mall/antomPay/payNotify` — 支付回调
- POST `/mall/antomPay/paymentResultInquiry` — 支付结果查询
- POST `/mall/antomPay/paymentCancel` — 取消支付
- （refund/refundInquiry/refundNotify 均已注释）

### AntomPayApiModeController — Antom 支付 API 模式（@Api Antom支付API模式，`/mall/antomPayApiMode`）
- POST `/mall/antomPayApiMode/getPayConsult` — 获取付款方式列表
- POST `/mall/antomPayApiMode/pay` — 创建付款订单

### EventSummaryController — 埋点数据统计接口（@Api 埋点数据统计接口，`/mall/event/summary`）
- POST `/mall/event/summary/recordPageView` — 记录页面访问 PV

### 内部 Feign：OrderManagementFeignController、MallOrderTaskFeignController（`/mall/orderManagement`）、AntomPayRecordFeignController（`/mall/antomPayRecord`）

---

## 9. tevaupay-fiat 法币模块

### FiatUSDController — USD 法币（`/fiat/usd`，无类级 @Api，开户/提现流程详尽）
- POST `/fiat/usd/apply/account` — (无描述)
- GET `/fiat/usd/va/info` — (无描述)
- GET `/fiat/usd/check/eligibility` — (无描述)
- GET `/fiat/usd/fees` — (无描述)
- GET `/fiat/usd/identity/verification` — (无描述)
- GET `/fiat/usd/va/bank/account` — (无描述)
- GET `/fiat/usd/withdraw/bank/supported` — 查询支持的提现银行列表
- POST `/fiat/usd/withdraw/bank/apply` — 【提现第1步】绑定提现银行账户 — 提现前需先绑定收款银行，返回银行账户 ID，绑定成功后调 GET /withdraw/bank/list 查看
- POST `/fiat/usd/withdraw/bank/edit` — 编辑提现银行账户 — 传入要编辑的 bankId 和新的银行信息，原银行账户将被标记删除，以新数据重新创建
- GET `/fiat/usd/withdraw/bank/list` — 【提现第2步】查询已审核通过的提现银行账户列表
- POST `/fiat/usd/withdraw` — 【提现第3步】发起 USD 提现 — 传入 bankAccountId(来自 bank/list) 和提现金额(最低5000USD)，校验余额→计算手续费→创建提现订单→扣减钱包→调用上游 API
- GET `/fiat/usd/withdraw/fee/preview` — 提现费用预览 — 传入提现金额，返回手续费和到账金额
- POST `/fiat/usd/cache/blacklist/refresh` — (无描述)
- GET `/fiat/usd/country/list` — 查询支持的国家列表 — type: 1=国家(含中国), 2=国家/地区(去掉中国)
- POST `/fiat/usd/liveness/result` — 【开户第3步】获取活体验证结果 — submit 返回 nextAction=1 时，用户完成人脸识别后调用
- GET `/fiat/usd/kyc/check` — 【开户第1步】KYC 匹配检查 — 进入开户页时调用，获取预填数据，返回 blacklisted 判断国家是否支持
- GET `/fiat/usd/kyc/checkWithScene` — 【开户第1步】KYC 匹配检查(带来源) — createScene: 1=充值, 2=提现(免开户费)
- POST `/fiat/usd/kyc/submit` — 【开户第2步】提交 KYC 申请 — 返回 nextAction: 1=需打开 livenessLink 做人脸验证；2=免人脸，直接调 /kyc/fee/pay 支付开户费
- GET `/fiat/usd/kyc/status` — (无描述)
- POST `/fiat/usd/kyc/fee/pay` — 【开户第4步】支付开户费 — 传入 applicationNo + 支付密码，从 USDT 钱包扣除开户费
- POST `/fiat/usd/deposit/activate` — 【入金开通】状态5用户付费开通入金账户
- GET `/fiat/usd/kyc/customerName` — 查询用户 KYC 姓名 — 返回最新一条 KYC 申请中的 customerName

### FiatWithdrawController — 法币提现（`/fiat/withdraw`）
- POST `/fiat/withdraw/details` — (无描述)
- POST `/fiat/withdraw/confirm` — (无描述)
- POST `/fiat/withdraw/confirm/rollback` — (无描述)

### FiatRechargeController — 法币充值（`/fiat`）
- GET `/fiat/recharge/pendingOrderList` — (无描述)
- GET `/fiat/recharge/orderDetails` — (无描述)
- POST `/fiat/recharge/details` — (无描述)
- POST `/fiat/recharge/confirm` — (无描述)
- POST `/fiat/recharge/uploadProcessingVoucher` — (无描述)
- POST `/fiat/recharge/uploadAuditVoucher` — (无描述)

### FiatPaymentController — （`/fiat`）
- GET `/fiat/paymentList` — (无描述)

### FiatCustomPaymentController — 自定义收款（`/fiat/custom`）
- GET `/fiat/custom/paymentList` — (无描述)
- GET `/fiat/custom/paymentDetails` — (无描述)
- POST `/fiat/custom/paymentSave` — (无描述)
- POST `/fiat/custom/paymentEdit` — (无描述)
- POST `/fiat/custom/paymentDelete` — (无描述)

### WalletExchangeController — 钱包兑换（@ApiOperation 钱包兑换，`fiat/walletExchange`）
- POST `fiat/walletExchange/fee/conversion` — 币种兑换费率
- GET `fiat/walletExchange/wallet/getCurrency` — 币种查询
- POST `fiat/walletExchange/current/conversion` — 币种兑换
- GET `fiat/walletExchange/current/balance` — 币种余额
- POST `fiat/walletExchange/supplement/fail/current` — 手动补数据
- POST `fiat/walletExchange/supplement/fail/tenantRecharge` — 企业充钱手动补数据
- GET `fiat/walletExchange/conversion/switch` — 币种兑换开关

### FiatInitController — （`/fiat/init`）
- GET `/fiat/init/wallet/createAccount` — (无描述)

### FiatTransactionMonitorController — 法币交易监控（`/fiat/monitor`）
- POST `/fiat/monitor/idrMonitor` — (无描述)
- POST `/fiat/monitor/idrMasterAccountMonitor` — (无描述)

### Webhook/内部 RPC（不对 APP 暴露）
- FiatUSDWebHookController（`/fiat/notice`，@Api callback 事件回调：payout/payment/swap/virtualBankStatus/userDeposit/userWithdrawal/blockchainWithdrawal/customerProfile/userBankAccountCreated/userBankAccountStatus/rfi）
- FiatWebHookController（`/fiat/webHook/callback` Fiat Webhook 事件回调）
- FiatFeignRpc（`/fiat`：handleUSDPayment 等）、FiatUSDAdminRpc（`/fiat/admin/usd`：refund/execute、kyc/review）、FiatScheduleFeignRpc（`/fiat/scheduled`）、FiatExchangeRpc（`/fiat/walletExchange`）

---

## 10. tevaupay-financing 理财模块

### FinancingController — 理财（`/financing`）
- POST `/financing/transfer` — 转账，钱包和理财账户互转
- POST `/financing/subscribe` — 理财认购
- POST `/financing/redeem` — 理财赎回
- POST `/financing/fee` — 查询手续费
- POST `/financing/checkSwitch` — 查询理财开关
- POST `/financing/checkConfig` — 查询是否黑名单
- POST `/financing/queryProductList` — 申购产品列表分页查询
- POST `/financing/userProductList` — 赎回产品列表分页查询
- GET `/financing/queryProductById` — 产品详情查询
- POST `/financing/queryBalance` — 查询余额
- POST `/financing/checkIsConfirm` — 校验是否已经确认过
- GET `/financing/policyConfirm` — 确认,0-拒绝，1-确认
- POST `/financing/records` — 交易/奖励记录
- POST `/financing/getTransferMinAmount` — 查询转账最低金额
- GET `/financing/queryTransferAmount` — 查询转账实际到账金额

### 内部 RPC：FinancingAccountFeignRpc（`/financing/financingAccount`）、EarnHourlyInterestRpc（`/financing/earnHourlyInterest`）

---

## 11. tevaupay-marketing 营销/活动模块

### InvitationStatisticController — 邀请统计（`/marketing/invitation/statistic`）
- GET `/info` 查询邀请统计数据、GET `/base` 查询邀请基本数据、GET `/level1Details` 查询邀请统计1级详情列表、GET `/level2Details` 查询邀请统计2级详情列表、POST `/subDetailsPage` 查询邀请统计下级详情列表、GET `/newBase` 查询新邀请基本数据

### RebateConfigController — 推荐返佣（@Api 推荐返佣，`/marketing/rebateConfig`）
- POST `/getRebateConfig` 获取返佣配置信息（多版本，含 1.1 版）、POST `/getRebateConfigDetail` 获取返佣配置详情、GET `/getFeignConfigTimeout`、POST `/getNewRebateConfig` 1.1版获取新返佣配置信息

### RebateStatisticController — 返佣统计（`/marketing/rebate/statistic`）
- GET `/info` 查询返佣统计数据、GET `/base` 查询返佣基本数据、GET `/details` 查询返佣详情列表、POST `/detailsPage` 查询返佣详情分页、GET `/newInfo` 查询新返佣统计数据、GET `/newBase` 查询新返佣基本数据、POST `/newDetails` 查询新返佣详情列表(1:0开卡,3充值)、GET `/allRebate` 查询总返佣数据

### PartnerInfoController — 合作方信息（@Api 合作方信息，`/marketing/partnerInfo`）
- POST `/marketing/partnerInfo/savePartnerInfo` — 保存合作方信息

### BankCardRewardRecordController — 开卡奖励记录（@ApiOperation 开卡奖励记录，`/marketing/cardRewardRecord`）
- GET `/marketing/cardRewardRecord/getCardRewardRecord` — 获取开卡奖励记录

### ExplorePageController — 探索页（`/marketing/explore`）
- GET `/marketing/explore/list` — 查询自定义探索页列表

### ActivityUserInviteKycController — （`/marketing/kyc`）
- POST `/marketing/kyc/addUserInviteKyc`、POST `/userInviteKyc1`、GET `/getInviteUserKycInfo` — 均(无描述)

### activity 子目录活动控制器
- VoucherDrawActivityController（代金券活动，`/marketing/voucher`）：generalUserLuckDrawData 初始化任务进度、voucherDraw 代金券抽奖、drawCount 获取当前用户可抽奖次数、sendVoucherInfo 发送交易活动信息、voucherPage 代金券记录、getRemainingAttempts 获取活动剩余次数、getActivityValidity 获取活动有效期、delCache
- PrizesController（活动抽奖，`/marketing/prizes`）：/record 查询活动用户抽奖记录、/raffle 抽奖、/initPrizes 初始化奖品池
- InvitationRewardsController（邀请奖励详情，`/marketing/activity`）：/invitation/rewards/details 查询邀请奖励活动数据
- BidController（竞拍活动，`/marketing/bid`）：/bid 竞拍、/listBidRecord 查询竞拍记录、/listBidPrizes 查询竞拍奖品、/getBidPrizesById 查询竞拍奖品详情、/queryEndTime 查询活动结束时间、/queryUserPrizesBidDetails 查询用户奖品竞拍详情、/queryPreviousWinner 查询上期活动获奖者
- BidUserTokenController（竞拍 token，`/marketing/bid`）：/tokenQuantity 查询用户竞拍 token 数量、/taskTypeTokenQuantity 查询用户每种任务得到的 token 数量、/generateToken 初始化用户 token 数量
- RecommendedRebateController（推荐返佣，`/marketing/activity/rr`）：/userInvitation/details 查询用户邀请数据、/userInvitation/getNowAmt 领取金额、/userInvitation/rankingList 排行榜
- ChristmasActiveController（圣诞新年活动，`/marketing/christmas/rr`）：/newYear/beforeKyc 判断是否新用户、/newYear/discountCode 获取优惠码、/newYear/userInvitation 查询用户待领取金额、/newYear/getNowAmt 领取金额、/newYear/awardRecords 奖励激励、/newYear/rankingList 排行榜、/newYear/queryTaskStatus 任务状态、/newYear/queryInviteFriends 新年消费活动
- ZNQController（周年庆，`/marketing/activity/znq`）：queryRanking 活动排行榜、queryRankingRewardRecord、queryRewardRecord、queryScrollBar 滚动条数据、queryTaskStatus、initUserTaskData、tipsAtTheTopOfRedEnvelopeVO、skipRedEnvelopePopUp、christmasSkipRedEnvelopePopUp、/initWeight、queryPictureStatus、sengRankingRewards、importPersonalRanking、importRanking
- ActivityBankCardController（累计邀请活动，`/marketing/activity`）：getCardInviteRewardInfo 获取卡邀请奖励信息、bindCardAddReward 绑卡成功添加奖励信息、claimRewards 领取奖励
- PhoneActivityController（手机购买活动，`/marketing/activity/phone`）：/initUserTaskData、/receiveReward、/queryRewardRecord、/queryActivityTaskStatus
- ActivityController（活动公共类，`/marketing/activity`）：/validateActivityBlackList 活动黑名单用户校验、queryInviteText 查询邀请注册文案、/validateActivityBlacklistAllLevels 活动黑名单用户校验所有下级
- BonusController（注册赠金，`/marketing/bonus`）：/status 查询赠金状态
- TotalInviteChallengeController（累计邀请活动，`/marketing/activity`）：/totalInviteChallenge/details 查询累计邀请挑战活动数据
- UserLuckDrawSourceController（抽奖来源，`/marketing/luckdraw`）：draw 领取抽奖次数、getDrawEntries 查询抽奖次数、getTasksSchedule 查询任务进度、getBonusCondition 查询奖金情况、getUserBonsConditionRecord 查询消费金记录、checkUserKyc 校验是否老用户kyc、checkUserRegist 校验是否老用户注册、queryRanking 排行榜、checkUserKycCard 校验kyc和开卡、generalUserLuckDrawData 初始化任务进度
- FinancingActivityController（理财活动，`/marketing/financingActivity`）：/baseInfo 查询活动基本信息、/rankingList 查询排行榜
- BlacklistAdminController（KOL 黑名单管理，`/marketing/admin/blacklist`）：/list、/add、/remove

### points 子目录
- PointsController（`marketing/points`）：generateBox、openBoxes、balance、code/redeem、redeem、box/pending、box/list、redeemConfig、transactions、code/create、code/batchCreate、job/expireBoxes、job/expireCodes、job/alertCheck — 均(无描述)

### 内部 Feign（不对 APP 暴露）
ActivityUserInviteKycFeignController、RebateRecordTaskFeignController、VoucherDrawActivityFeignController（voucherExpired 代金券过期）、ExchangeRebateFeignController、NewRebateRecordFeignController、StockRebateFeignController、ActivityFeignController、CompensationScheduleFeignController、RegisterBonusFeignController、BankCardRewardRecordFeignController、FinancingActivityFeignController、UserInvitationLevelUpdateRuleFeignController、BankCardRewardConfigFeignController、RebateRecordFeignController（开卡返佣等）。

---

## 12. tevaupay-external 对外开放接口模块（下游/第三方调用，非 APP 持卡用户）

- ExternaSkyDaolKycController（`/external-api/v1/kyc/submitKycData` 提交KYC认证数据）
- CardInfoController（`/v1/card/checkCardPermission` 客户id查询此客户是否允许做开卡、卡充值）
- UserNotifyNoticeController（`/external-api/v1/kyc`：kycNotify、notifyUserBaseInfoChange）
- ExternalUserController（`/external-api/v1/user`：register、login、phoneNotify、emailNotify）
- WotKycController（`/external-api/v1/kyc`：submitKycDataInfo、getKycUrl、getUserKycInfo）
- WotUserController（`/external-api/v1/user`：getUserInfo、saveUserInfo、updateUserInfo、getUserSetting、updateUserSetting、saveUserSetting）
- WotCountryAreaPhoneController（`/external-api/v1/countryAreaPhone`：getCountryAreaList、getPhoneCodeList）
- WalletController（external，`/v1/account/accountNotify` 预备金扣除成功回调通知）
- ExternalWalletController（`/external-api/v1/wallet`：queryWalletCurrencyBalance、balance、getCurrencyBalanceList、getCommonData、getTxResult、getFee、getCurrency、getNetwork、getAddress、withdraw、transfer、page、walletDetails、optAccount、createOrder、updateOrderStatus、idrPendingDetails、idrDetails）
- 内部 Feign：SkyDaoUserFeignController、ExternalUserCallbackController、ExternalFeignController

---

## 13. tevaupay-data-statistics 数据统计/代理商后台模块（partner 后台，非 C 端持卡用户）

partner 目录控制器服务于代理商后台（独立 SaToken 登录，PartnerLoginConfig）。主要：PartnerController（login/loginOut/getValidateCode/getAsyncRoutes/getUserInvitationLevel）、SubordinateDetailsController、WalletAgentController、RechargeStatController、PartnerAgentCardController、LookPlateController、ExceptionDataStatisController、DictInfoController、CardInactiveFeeDeductionController；dataCount/DataCountController（运营日报）。多为代理商/运营数据，不在 C 端 APP 范围。

---

## 14. tevaufinance-investment 证券投资模块（C 端 APP 证券功能）

证券交易/行情功能，APP 证券 Tab 使用。

### tevaufinance-investment-data（行情/自选/搜索/站内信，APP 直连）
- StockWatchlistController（自选股票管理，`investmentData/watchlist`）：add 收藏股票、remove 取消收藏、batchRemove 批量删除自选、list 查询自选列表(含实时行情)、moveToTop 置顶股票、reorder 拖动排序、isWatched 查询是否已收藏
- StockSearchController（股票搜索，`investmentData/stock/search`）：POST `` 股票模糊搜索、history/save 保存搜索历史、history/list 查询搜索历史、history/batchRemove 批量删除搜索历史、history/clearAll 清空全部搜索历史、history/statistics 导出搜索历史统计CSV
- InvestmentMessageController（站内信管理，`investmentData/message`）：hasUnread 红点查询、list 消息列表、toggleRead 切换已读/未读、readAll 全部已读、batchDelete 批量删除
- UserAgreementController（用户条约阅读，`investmentData/userAgreement`）：read 确认阅读条约、check 查询是否已阅读条约
- SecurityBaseInfoController（`investmentData/base`）：getQuote 获取股票基本行情、selectedUsList 获取精选美股榜单、indexList 获取指数列表、getTradeQuote 获取股票交易行情、getMarketStatus 获取股票市场状态 等（含多个 init/refresh 初始化运维接口）
- SecurityDataKlineController（`investmentData/kline/query` 查询K线数据，支持 1min~1month）
- SecurityContractInfoController（`investmentData/contract/get` 获取股票合约下单信息）
- StockIntradayMinuteUsController（美股分时数据，`investmentData/intradayMinute`：query 查询分时图数据、priceList 查询分时图价格数组 等）
- TradeTickInitController（`investmentData/tradeTick/query` 查询逐笔成交数据-瀑布流）
- SecurityOrderBookController（`investmentData/orderBook/latest` 获取最新订单簿）
- StockSectorController（板块，`investmentData/sector`：list 查询板块列表 等）
- WhitelistController（`investmentData/whitelist`：check 判断是否白名单用户 等）
- TevaufinanceEventController（`investmentData/event/record` 记录埋点事件）
- 各周期 K 线初始化控制器（SecurityData1min/5min/15min/1hour/2hour/3hour/4hour/1day/5day/1week/1month KlineController、SecurityDataBatchKlineController）：均为 init 运维初始化接口
- 行情订阅/迁移/日历：SecurityDataSubscribeController、KlineMigrationController、SecurityTradeCalendarController、StockChangePctController（多为内部）

### tevaufinance-investment-trans/settlement/positions（交易/结算/持仓）
- StockOrderController（股票交易订单，`.../stockOrder`）：/preOperate、/submit、/cancel、/modify
- QueryStockOrderController（股票订单查询，`.../queryStockOrder`）：/classify、/history、/detail
- StockAssertController（股票资产，`.../stockAssert`）：/assetOverview、/maxBuyingPower、/assetDetail、/queryTransferBalance 查询转账页双账户余额、/manualTransfer 手动划转(Finance→Wallet)、withdraw 提币
- OrderFeeController（订单手续费，`.../orderFee`）：/estimateCalculate、/maxShares
- StockPositionController（持仓信息，`.../position/queryUserPosition`）

### tevaufinance-investment-adapter / websocket（券商适配 + WS，多为内部）
- WsTokenController（`/investmentWsApi/token` 获取 WebSocket 一次性 Token，APP 用）
- TigerSubscribeController、SecurityKline/Info/Market/Contract Controller、AdapterStockOrderOperateController、TigerOrderCallbackController、TradeTickController（券商适配内部接口）

---

## 15. xxl-job-admin / tevaupay-mq-consumer / tevaupay-oms（非 APP）

- xxl-job-admin：定时任务管理后台（JobGroupController/JobInfoController/JobLogController/JobCodeController/JobApiController/UserController/IndexController），运维后台，非 C 端。
- tevaupay-mq-consumer：MqTest（`/mq/test/test`），测试接口。
- tevaupay-oms：UserController（`/user/addUser`、`/getUserList`），OMS 内部。

---

## 16. 对「客服 AI 查 C 端用户数据」最有用的接口

以下接口可直接回答客服高频问题（卡为什么被锁、转账/充值失败、实名状态、余额、交易明细等）。这些是 APP 对外接口；若 AI 走内部数据，对应 Feign 内部接口（标注）通常更适合后台只读查询。

### 卡状态 / 卡为什么被锁、被冻结、被注销
- POST `card/bankCardUser/getCardDetail` — 获取卡详情（不传 id 返回默认卡）：卡状态、别名等。
- POST `card/bankCardUser/getCustBankcard` / GET `card/bankCardUser/getCustBankcardDetail` — 客户银行卡信息及详情（状态描述、卡方状态）。
- POST `card/bankCardUser/getCardDetailInfoById`（V11000）— 详细状态信息 + 物流，能解释「卡为啥锁/制作中/物流到哪」。
- POST `card/bankCardUser/getCardStatusById` — 根据卡 id 获取卡片状态。
- GET `card/bankCardUser/getCardStatusAndWalletStatus`（V11000）— 申请卡状态 + 钱包状态。
- POST `card/bankCardUser/getApplicationRecord` — 申请卡记录（开卡进度/失败可查）。
- POST `card/bankCardUser/lockCard` / `cancelCard` — 锁卡/解锁、注销（动作类，排查近期是否被操作）。
- 内部 Feign（后台只读更合适）：`BankCardUserFeign.getBankCardUser` / `getBankCardUserByCardNumber`(根据卡号取详情) / `getBankCardUserByUserId` / `queryCardInfoListByUserId`(用户名下所有卡) / `getFreezeHistory`(用户冻结历史，直接回答"卡为啥被冻结") / `getUserValidCardNum` / `getCardHolderUserInfo`。`CardMgmtBankCardUserFeign` 含 cardFrozen/cardMgmtCardStatus（人工冻结/状态变更来源）。

### 用户 / KYC 实名状态
- GET `user/userKyc/getKycInfo` — 获取 kyc 认证信息（实名状态/等级）。
- POST `user/userKyc/getLevel2Result` — KYC 二级验证结果。
- POST `user/userKyc/getKycCertificationProcess` — kyc 认证流程进度。
- POST `user/getCurrentUserInfo` — 当前用户基础信息。
- GET `user/queryByEmailOrInviteCode` — 按邮箱/邀请码定位用户（找人）。
- 内部 Feign（后台只读）：`UserFeign.getUserKycInfo` / `getUserById` / `getUserByCode` / `getUserBaseInfo` / `UserBaseInfoInitionInfo`；`UserKycFeign.getUserKycInfoDto`；`UserFeign.getUserKycNum` / `getSubKycQuantity`。

### 余额查询（钱包 / 卡 / 理财 / 法币）
- GET `/wallet/getBalance` / `/wallet/getCurrentBalance` / `/wallet/getCurrencyBalance` / `/wallet/getCurrencyBalanceList` — 钱包/币种余额。
- GET `/wallet/getTotalAssets` — 钱包总资产。
- GET `/wallet/queryWalletCurrencyBalance` — 钱包币种余额。
- POST `/financing/queryBalance` — 理财余额。
- GET `fiat/walletExchange/current/balance` — 法币兑换币种余额。
- 内部 Feign（后台只读）：`WalletFeign.queryUserBalance` / `getBalance` / `getCurrentBalance` / `getTotalAssets` / `queryWalletCurrencyBalance`；`CardAccountingFeign.getAccount` / `getAccountByNumber` / `getAccountList`（卡账户余额，回答"卡里还有多少钱"）。

### 交易明细 / 转账失败 / 充值失败 / 退款
- POST `/trans/records/page`（及 TransV11000Controller `/trans/records/page`）— 交易分页列表。
- GET `/trans/records/transactionDetails` — 交易详情。
- GET `/trans/records/getSingleTransaction` — 单笔交易（排查某笔失败）。
- GET `/trans/records/queryAccountBalance` — 账户余额（交易侧）。
- POST `card/bankCardTransaction/getBankCardTransactionDetail` — 卡交易详情信息（卡消费明细，能回答"这笔扣款是什么"）。
- POST `/trans/wallet/page` — 钱包交易记录。
- GET `/wallet/getTxResult` — 提币/转账结果查询（直接回答"我的转账/提币到账没"）。
- POST `/order/page` / GET `/order/queryByOrderId` / `/order/walletDetails` / `/order/idrDetails` — 业务订单（充值订单）查询。
- 法币订单：GET `/fiat/recharge/pendingOrderList` / `/fiat/recharge/orderDetails`、`/fiat/usd/kyc/status`、`/fiat/usd/withdraw/...`（法币充值/提现进度与失败原因）。
- 卡账单统计：POST `/trans/statistics/monthlyBilling`（近6月账单）、`/trans/statistics/transSuccessRate`（近6月交易成功率，回答"为什么老是失败"）、`/trans/statistics/merchantCountryDistribution`。
- 内部 Feign（后台只读）：`TransFeign.queryWalletRecord` / `queryWalletRecordById` / `queryWalletRecordByBusinessNo`；`TransCardFeign.queryRecordByOrderId` / `queryCardRecordInfo` / `queryCardBalance` / `getLatestSuccessfulTransaction` / `getSingleTransaction`；`CardRefundFeign.getRefundDetailsById` / `queryPendingRefundList`（退款进度）。

### 物流 / 实体卡进度
- POST `card/bankCardLogistics/getBankCardLogistics` — 银行卡物流信息（实体卡寄到哪了）。
- POST `card/bankCardUser/getCardDetailInfoById`（V11000）— 含物流。

### 安全设置（支付密码/谷歌验证，回答"为什么验证不过/被锁"）
- GET `/user/userSetting/getSettingStatus` — 支付密码、谷歌验证码状态。
- 内部 Feign：`PaymentCodeFeign.validatePaymentCode`、`GoogleCodeFeign.getGoogleTokenStatus`。
