# 聊天双向图片（截图）支持 — 设计文档

日期：2026-05-26

## 1. 目标与范围

让聊天对话框支持发送图片（截图），并让 AI 能识别图片信息。需求确认：

- **双向**：C 端（APP webview）和 B 端（商户 OpenAPI）用户都能发图片给 AI / 客服；客服人员也能直接发图片给用户。
- **AI 识别**：用户发的图片要传给 LLM（`claude-sonnet-4-6`，支持 vision）做识别。
- **客服可见**：转人工 / 旁观 / 会话日志场景，客服都能看到用户发的截图。

### 范围外（YAGNI）

非图片附件（PDF/视频）、OCR 预处理、缩略图生成/压缩、CDN、病毒扫描、图片编辑。本期不做。

## 2. 关键约束（来自现状代码）

- SSE 主链路 `GET /api/v1/chat?message=...` 把消息放在 URL query，**图片二进制放不进去**。
- 消息落库 `messages.content` 是 TEXT 字符串列；assistant 行已有"content 存 JSON 块"的先例（`runtime._history_text` 会 `json.loads`）。
- **生产是多实例 / 会水平扩容** → 本地文件卷不共享，**必须用对象存储**。
- 当前无对象存储基建（无 S3/OSS/MinIO），但 `python-multipart` 已装，可直接收 multipart 上传。
- 客服→用户消息走 `POST /staff/api/v1/conversations/{cid}/messages`（`body.content` 字符串）+ `_human_message_event` 经 SSE 回推。
- 前端原则：不本地乐观 push，消息一律靠后端 SSE 事件驱动回显（见 `chatEvents.ts`）。

## 3. 架构总览

```
用户/客服选图
  → POST .../attachments (multipart)         [上传，落对象存储 + attachments 表，message_id=NULL]
  → 返回 {attachment_id}
  → 发送消息时带 attachment_ids
     · 用户: GET /api/v1/chat?...&attachment_ids=1,2
     · 客服: POST /staff/.../messages  body 带 attachment_ids
  → 后端校验(会话一致 + 未绑定 + 上传者匹配) → 绑定到该 message 行
  → AI 轮: run_turn 读对象存储转 base64 注入 LLM
  → 回显: 用户/human_message 事件带 attachments 元信息 → 前端渲染缩略图
  → 看图: GET .../attachments/{aid} → 鉴权 → 302 到短时效预签名 URL
```

## 4. 存储层（对象存储，S3 兼容）

新增模块 `server/src/ai_engine/storage/object_store.py`，定义抽象接口：

```python
class ObjectStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...            # 给 LLM base64 用
    async def presigned_get(self, key: str, ttl_seconds: int) -> str: ...  # 给浏览器看图用
```

- 实现走 **S3 兼容**（`aioboto3`）。dev 在 `docker-compose.yml` 加 **MinIO** 容器；生产用环境变量指向 OSS（S3 兼容端点）或 S3。
- 新增配置（`config.py` + `.env`）：`OBJECT_STORE_ENDPOINT`、`OBJECT_STORE_BUCKET`、`OBJECT_STORE_ACCESS_KEY`、`OBJECT_STORE_SECRET_KEY`、`OBJECT_STORE_REGION`（可空）。
- object key 规则：`uploads/{conversation_id}/{uuid}.{ext}`。
- 新增依赖：`aioboto3`。

## 5. 数据模型

新增 `attachments` 表（建表语句加进 `init_db`）：

| 列 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | |
| conversation_id | INTEGER | 所属会话，鉴权用 |
| message_id | INTEGER NULL | 绑定的消息行；上传时为 NULL，发送绑定后写入 |
| uploader_type | TEXT | `c` / `b` / `staff` |
| uploader_id | TEXT | subject_id 或 staff sub，校验绑定者匹配 |
| object_key | TEXT | 对象存储 key |
| mime | TEXT | image/png 等 |
| byte_size | INTEGER | |
| sha256 | TEXT | 去重/审计 |
| created_at | TEXT | |

`messages.content` 列**不动**，保持纯文本（图片消息文本可为空串）。附件靠本表关联。理由：所有把 content 当字符串读的地方（`sum_content_chars` 的 `LENGTH(content)`、replay、staff 列表）零改动，只在需要处 JOIN。

新增 DAO（`persistence/conversations.py` 或新 `persistence/attachments.py`）：
- `create_attachment(conv_id, uploader_type, uploader_id, object_key, mime, byte_size, sha256) -> int`
- `bind_attachments(message_id, conv_id, uploader_id, attachment_ids) -> list[dict]`：原子校验"属于本会话 + message_id 仍为 NULL + uploader 匹配"，命中才更新 message_id；返回成功绑定的行。任一不满足则该 id 跳过（不报错中断整轮）。
- `list_message_attachments(message_id) -> list[dict]`
- `list_attachments_for_conversation(conv_id) -> dict[message_id, list]`：客服历史/日志批量取。

## 6. 上传端点（multipart）

校验（两端共用一个 helper）：
- mime 白名单：`image/png`、`image/jpeg`、`image/webp`、`image/gif`。
- **magic-byte 嗅探**实际字节头，不只信 Content-Type。
- 单图上限 **5 MB**；超限 413。
- 类型不符 415。

端点：
- 用户侧 `POST /api/v1/conversations/{cid}/attachments`：`_authorize_conversation` 鉴权（C/B/游客归属校验）。落对象存储 + `create_attachment(message_id=NULL)`。返回 `{attachment_id}`。
- 客服侧 `POST /staff/api/v1/conversations/{cid}/attachments`：`require_staff` + 担当校验。同上，`uploader_type="staff"`。

单条消息最多 **4 张**图（前端限制 + 后端绑定时截断校验）。

## 7. 看图端点（鉴权 + 预签名重定向）

`GET /api/v1/conversations/{cid}/attachments/{aid}`：
- 用户侧 `_authorize_conversation`，客服侧另设 `GET /staff/api/v1/conversations/{cid}/attachments/{aid}` 走 `require_staff`+担当。
- 校验 attachment 属于该会话 → `presigned_get(key, ttl=300)` → **302 重定向**到预签名 URL。
- 浏览器直连对象存储拉字节，api 不代理大文件，多实例无压力。
- 预签名 URL 短时效（5 min），不交给 Anthropic（见下）。

## 8. 发送流程与绑定

### 用户 → AI / 客服
- 前端先上传图片拿 `attachment_id[]`，再调 `streamChat`，在 query 加 `attachment_ids=1,2`（仅 id，小，GET 可承载）。
- `GET /api/v1/chat` 新增 `attachment_ids: str | None` query 参数（逗号分隔）。
- 在创建本轮 user 行（`append_user_turn`）后，调用 `bind_attachments(message_id, conv_id, subject_id, ids)` 绑定。
- 幂等重放（`client_message_id` 命中）时，附件已绑定在历史行上，重放不重复绑定。

### 客服 → 用户
- 客服先上传拿 id，再 `POST /staff/.../messages`，`StaffMsgIn` 增加 `attachment_ids: list[int] = []`。
- `append_human_message` 后 `bind_attachments(message_id, conv_id, staff_sub, ids)`。
- `_human_message_event` 增加 `attachments` 字段（每项含 `attachment_id` + `mime`；URL 由前端用看图端点拼）。

`content` 允许空串（纯图片消息）；后端发送校验改为"文本非空 **或** 有附件"。

## 9. 注入 LLM（vision）

`runtime.run_turn`：本轮若有绑定附件，把 user 消息组装成内容块：

```python
content = []
for att in attachments:
    raw = await object_store.get(att["object_key"])
    content.append({
        "type": "image",
        "source": {"type": "base64", "media_type": att["mime"],
                   "data": base64.b64encode(raw).decode()},
    })
if user_message:
    content.append({"type": "text", "text": user_message})
messages.append({"role": "user", "content": content})
```

- 鉴权/预签名 URL 后端 Anthropic 拉不到，且口径上不把敏感图交公网，统一用 **base64**。
- `_load_history` 重建历史时，同样对带附件的 user 行重新读对象存储转 base64 注入（每次都发，token 成本上升——见 §12）。
- **话题分类 / 语言判定只用文本部分**；纯图片消息（文本空）：跳过话题分类（视为放行），locale 保留上轮。

## 10. 前端

### 类型
`web/src/types.ts`：
- `Message` 的 `user` / `assistant` / `human_agent` 变体增加 `attachments?: { id: number; mime: string }[]`。
- `ChatEvent` 的 `human_message`、新增的 user 回显事件携带 `attachments`。
- 渲染时用 `GET .../attachments/{id}` 作为 `<img src>`（浏览器自动跟随 302）。

### 组件
- `MessageBubble`：渲染图片缩略图（圆角、最大宽度约束），点击全屏放大（lightbox，可用现有 ui 组件或简单 overlay）。
- `InputBox`（用户）：加图片附件按钮（`<input type=file accept=image/*>`）+ 粘贴板贴图（paste 事件）。选图后先调上传 API，展示待发缩略图（可删除），发送时把 id 传给 `onSend`。
- `TakeoverFooter`（客服）：同样加附件按钮 + 上传 + 发送带 id。
- `useChat` 的 `send` 签名扩展为 `send(text, attachmentIds?)`；`api/chat.ts` 的 `streamChat` 与 `sendStaffMessage` 增加 `attachmentIds` 参数。
- 上传 API 封装：`uploadAttachment(conversationId, file) -> {attachment_id}`（用户/客服各一个，走对应 authedFetch）。

### 回显
- 保持"不本地乐观 push"：自己发的图也等 user / human_message SSE 事件回推后再渲染。
  - **注意**：当前用户发文本是在 `useChatSend` 里本地 `setMessages` 追加 user 行（见 `useChat.ts:135`），并非纯 SSE。为最小改动，沿用此本地追加方式，把 attachments 一并带进本地 user 行（与既有文本行为一致），不破坏现有约定。

## 11. 客服控制台可视化

- `ConversationDetailRoute` / `ConversationLogsRoute`：拉历史时用 `list_attachments_for_conversation` 合并 attachments，渲染图片。
- `SpectateRoute`：旁观流 `publish_conversation_event(user_message)` 事件带上 attachments 元信息。
- staff 侧看图走 `GET /staff/api/v1/conversations/{cid}/attachments/{aid}`。

## 12. 成本与性能

- vision + 历史每轮重发 base64 图片 → token 成本上升。本期靠现有会话压缩（`_maybe_compact`）兜底：老会话被总结后图片自然退出上下文。
- 不做缩略图压缩（YAGNI）；5MB 上限 + 4 张约束控制单轮体量。
- 可选优化（本期不强制）：给带图 user 轮加 `cache_control` 命中 prompt 缓存，降低多轮重发成本。

## 13. 测试

- 后端：上传校验（mime/magic-byte/大小/数量）、绑定鉴权（跨会话越权、重复绑定、上传者不匹配）、看图端点鉴权 + 302、run_turn 注入 base64（mock object_store）、纯图片消息绕过话题分类、客服双向。
- 前端：上传交互、缩略图渲染、粘贴贴图、send 带 attachmentIds、human_message 带图渲染。
- 复用现有测试基建（`server/tests/`、`web/tests/`）。

## 14. 跨端同步检查

改动跨 backend + web（C/B 用户侧 + 客服侧）。本设计已覆盖三处的对应改动（上传/绑定/看图端点、LLM 注入、前端 InputBox/TakeoverFooter/MessageBubble、客服控制台）。无 Flutter 改动（C 端是 webview，文件选择走标准 `<input type=file>`，若 APP webview 不支持需 APP bridge 拍照——本期先用标准 file input，APP 侧能力另议）。
