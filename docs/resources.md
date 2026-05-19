# 资源与环境

AI 引擎对接的代码仓库与测试环境。**密码不进本文档**，所有凭证统一在 `.env`（被 `.gitignore` 忽略）。

## 代码仓库（GitLab `test` 分支）

| 仓库别名 | URL |
|---|---|
| `openapi_backend` (Nexus) | https://gitlab.tevaupay.com/tevaupay/business-services/TevauNexus-Service/tree/test |
| `app_frontend` (Flutter) | https://gitlab.tevaupay.com/tevaupay-views/app/TevauPay-Flutter/tree/test |
| `app_backend` | https://gitlab.tevaupay.com/tevaupay/business-services/TevauPay-Service/tree/test |

部署时 clone 这 3 个仓库到 `repos/<仓库别名>/`，引擎从 `CODE_REPOS_ROOT` 配置项读取根目录。

## 测试数据库（阿里云 RDS Singapore — 单实例，多库）

**单 RDS 实例**，两个网络入口：

| 入口类型 | host | port | 用途 |
|---|---|---|---|
| 内网 | `rm-gs5bk11j43yl6jxt4.mysql.singapore.rds.aliyuncs.com` | 3306 | 生产服务器接入 |
| 公网 | `rm-gs5bk11j43yl6jxt40o.mysql.singapore.rds.aliyuncs.com` | 61306 | 本地调试 |

> 之前文档以为这是两个独立实例 + 库名 `nexus_test`/`tevau_test`，**错误**。2026-05-19 用户截图（业务方维护的"DB 连接清单"）澄清：单实例、多业务库、内/外网双入口。

**库 + 账号清单**（5 个库在同一实例上）：

| 库名 | 用途 | 推荐账号 | 项目 | AI 引擎是否接 |
|---|---|---|---|---|
| `unlimitpay_test` | **Tevau 主业务库**（卡片 / 用户 / 订单 / API 调用日志等核心数据） | `tevau_test_read`（**只读**，AI 引擎必用） | tevau | ✅ MVP-2 主接 |
| `nexus_test` | Nexus 项目业务库 | `nexus_test`（注：此账号不是只读，慎用，待 DBA 配只读账号） | nexus | ✅ MVP-2 次接 |
| `wot_app_test` / `wot_manage_test` / `wot_develop_test` | wot 项目（3 个库共用账号） | `wot_test` | wot | ❓ 待用户确认是否需要 |
| `t_tevau_api_saas` | Tevau SaaS 项目 | `tevau_saas` | tevau_saas | ❓ 待用户确认是否需要 |

**AI 引擎接入约束**：
- 强制走 spec §5.5 "业务只读库" 路径，**每个库一个独立连接池**，禁止跨库 join
- `unlimitpay_test` 必须用 `tevau_test_read` 账号（只读）；不允许用读写账号 `tevau_test`
- `nexus_test` 项目库在生产前需要 DBA 配一个 `*_read` 只读账号

密码：见本机 `.env`（参考 `server/.env.example`），或问 z2674818693@gmail.com。**不要把密码写进任何 git 文件**。

## 凭证管理约定

- `.env` 必须在 `.gitignore`，禁止提交
- `server/.env.example` 进 git，但只放 key 名 + 空值占位
- 生产凭证不与测试凭证混用，分文件管理（如 `.env.prod` / `.env.test`）

## 待对接

- B 端登录方案（SSO 或独立账号）
- 另一对接人姓名（值班表 = 嘉豪 + ?）
- SLA 数值表（由事项中心配置）
- DB 工具完整白名单与字段脱敏规则（见 spec §5、§12）
