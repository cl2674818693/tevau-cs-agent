# 身份与鉴权机制（C 端 / B 端）—— 客服 AI 系统对接结论

> 来源：通读 TevauPay-Service（C端）/ TevauNexus-Service（B端）后端代码（2026-05-21）。
> 结论直接影响本项目已写的 `auth/c_jwt.py`、`auth/bu_session.py` —— **原 RS256 JWT 方案不适用，需改**。

## C 端（APP 终端用户）—— Sa-Token + Redis，不是 JWT

- 网关用 **Sa-Token 框架**（`tevaupay-gateway/config/SaTokenConfig.java`），依赖 `sa-token-spring-boot-starter` + **`sa-token-redis`**（无 `sa-token-jwt`）。
- 即：登录后签发的是 **Sa-Token 随机会话 token**（不是 JWT，本地无法解析/验签），`token → loginId(=userId)` 的映射存在 **Redis**。
- token 经 header 传递，header 名 = `sa-token.token-name`（在 nacos 远程配置，yml 里没硬编码）。
- 登录方式：第三方为主 —— **Line**（`LineJwtValidator`）、**Firebase**（`RedisFirebaseJwtValidator`）、**Google Authenticator**（2FA）。登录入口在 `tevaupay-user`（`ThirdLoginController` 等）。
- 用户身份字段：Sa-Token 的 loginId 对应 `t_tevaupay_user.id`（bigint）。
- 注：`tevaupay-common/utils/JwtUtil.java` 是**示例占位类**（SECRET_KEY 写死 "your-256-bit-secret-key-here"），**未实际用于 C 端登录**，不要被它误导。

### 对我方客服系统的含义（C 端）—— 对接路径已打通（查 Flutter APP 代码确认）
完整链路（`tevau-pay-flutter`）：
1. APP 登录（`POST /user/login`，第三方 Line/Firebase/Apple）→ 后端 Sa-Token 签发会话 token → APP 本地存 `token`。
2. APP 内嵌客服 h5 → 通过 **js_bridge**（`lib/core/webview/js_bridge.dart`，返回 `{'token': token}`）把 token 注入 h5。
3. 请求时 token 放 **`Authorization` header**（`lib/core/network/interceptors/auth_interceptor.dart`：`options.headers['Authorization'] = _token`）。
4. 后端 Sa-Token 校验，**`StpUtil.getLoginIdAsLong()` = userId（Long）= `t_tevaupay_user.id`**。
5. **现成的换取用户信息接口：`POST /user/getCurrentUserInfo`**（带 Authorization、body `{}`），返回 UserInfoResp（含 userCode/kycStatus/email 等）。

**我方客服系统对接方案（推荐）**：拿 h5 经 js_bridge 传来的 token → 带 `Authorization` 调 `POST /user/getCurrentUserInfo` → 拿到用户身份 → 作为 C 端 subject_id 查 `unlimitpay_test`（按 `user_id` 隔离）。**不必本地验签、不必共享 Redis**。
- `auth/c_jwt.py`（RS256 验签）整体替换为"调 getCurrentUserInfo 换身份"；`APP_JWT_PUBLIC_KEY` 作废。
**已确认**：`UserInfoResp`（后端 VO）**只有 `userCode`，无数字 userId**。所以我方对接多一跳：token → `getCurrentUserInfo` 拿 `userCode` → 查 `t_tevaupay_user WHERE user_code=? 得 id` → 用该 `id`(=user_id) 查 card/kyc/transaction 等表（按 user_id 隔离）。全程无需后端改动 / 共享 Redis / 验签。

## B 端（BU 企业合作伙伴 OpenAPI）—— apiKey + 签名

- 网关 `tevau-nexus-gateway` 的 `ValidateServerImpl` 做**签名鉴权**：校验 apiKey/appId + signature + timestamp + nonce（防重放，`GatewayConfig.signatureTime=5` 分钟）。
- **tenant_id 来源**：`BaseRequestGlobalFilter` 用请求的 apiKey → 查 `companyConfig`（`GetCompanyConfigInfoResp`）→ `companyConfig.getTenantId()`。Redis 缓存 key：`nexus:server:tenant:xapiKey:%s` / `tenant:token:%s` / `tenant:ip:%s`（含 IP 白名单）。
- tenant_id 形如数字串 `1011010000190`（见网关测试代码注释 `tenant-id", "1011010000190"`），关联业务库 `tevau_nexus_test.*` 的 `tenant_id varchar(32)`。

### 对我方客服系统的含义（B 端）
我方 B 端身份目前是 BU 登录（cookie/`X-BU-ID`，本地写死 `BU00243780`）。要查真实库,必须把 **BU 标识映射成真实 `tenant_id`**（`BU00243780` 这种编号 ≠ 数字串 tenant_id）。方案：
1. BU 登录时拿到/绑定其 tenant_id（查 company 配置表）；或
2. 我方直接用 tenant_id 作为 B 端 subject_id。
> 待确认：BU 编号（如 BU00243780）与 tenant_id 的对应关系存在哪（company 配置表？哪张表）。

## 对现有代码的改动清单（待办）
- `auth/c_jwt.py`：RS256 JWT 验签 → 改为 Sa-Token 会话校验（共享 Redis 或调 user 后端接口）。`APP_JWT_PUBLIC_KEY` 配置项作废。
- `auth/bu_session.py` / `tool_router`：B 端 subject_id 需是真实 `tenant_id`；查询工具按 `tenant_id` 隔离（不是 `bu_id`）。
- 业务查询工具：按真实表重写（见 [[business-db-schema]] / 探查报告），C 端按 `user_id`、B 端按 `tenant_id` 隔离。
