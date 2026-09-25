# WebUI API 端点一览

管理面板全部 HTTP / WebSocket 端点的参考文档。路由实现按功能域拆分在 `routes/` 包内（每个模块对应一个前端页面），由 `panel_router.py` 聚合挂载到 `/admin` 前缀下。本文可作为前端开发、脚本调用与二次开发的复用素材。

## 通用约定

### 基础地址

所有 API 路径都挂在 `/admin` 前缀下，例如完整路径为 `/admin/api/status`。下文表格只写 `/api/...` 相对路径。

### 鉴权模型（除标注"免鉴权"外全部需要）

面板采用「登录换发会话令牌」：

1. 先调用 `POST /api/login`，用**主令牌**（面板口令）换取**会话令牌**；
2. 之后所有请求携带会话令牌——HTTP 端点用 `Authorization: Bearer <session_token>`；
3. WebSocket 不能带自定义请求头，采用**一次性票据**：先 `POST /api/ws_ticket`（会话令牌鉴权）拿 `ticket`，再用 `?ticket=<ticket>` 建连（30 秒有效、单次使用；旧 `?token=<session_token>` 仍兼容）；
4. `<img>`/`<audio>`/`<video>` 标签既不能带请求头也不能先取票，仍用 `?token=<session_token>`（配合 `Referrer-Policy: no-referrer` 防 Referer 外泄）。

- 主令牌来源优先级（`deps.py::_access_token`）：
  1. `config.json` 的 `web_panel.access_token`
  2. 环境变量 `ATRI_PANEL_TOKEN`
  不会回退到平台 `access_token`；未配置主令牌时接口返回 503。
- 弱主令牌：长度不足 16 字符、或与平台 `access_token` 相同时只告警不阻断；把 `web_panel.block_weak_token` 设为 `true` 后，登录端点会直接 403 拒绝（防弱口令猜解）。
- 会话令牌：内存态存储（进程重启失效）、**固定有效期**（默认 4 小时，可由 `web_panel.session_ttl_hours` 调整为 1-24 小时，签发后计时、不滑动）、容量上限 100；`POST /api/logout` 可即时吊销；主令牌轮换（改配置/环境变量）会立刻清空全部会话与未用票据；前端在到期时刻自动退出登录。
- 已建立的 WebSocket 会周期性复验会话，吊销/过期后以 4401 断开。
- 所有 `/admin*` 响应带安全头（`X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: no-referrer`、CSP `frame-ancestors 'none'` 等），`/admin/api/*` 强制 `Cache-Control: no-store`。

### 防暴力破解（仅登录端点）

`POST /api/login` 采用**全局统一计数**（不区分来源 IP）——连续失败 1-2 次返回 401（附剩余尝试次数），第 3 次起触发锁定，时长 `10 分钟 × 2^(连续失败次数-3)` 封顶 24 小时；**锁定期内所有登录请求一律 429（正确口令也拒绝）**，期间新的失败不计数、不续期；登录成功清零。计数与锁定为进程内存态，重启 bot 即清空。会话令牌为 256 位随机值，不参与失败计数。

### 统一错误格式（FastAPI 标准）

```json
{ "detail": "错误描述" }
```

| 状态码 | 含义 |
|---|---|
| 400 | 参数非法（detail 中带具体原因） |
| 401 | 会话令牌无效/过期（重新登录获取）；登录端点则为主令牌错误 |
| 404 | 资源不存在 |
| 413 | 上传文件超过大小限制 |
| 429 | 登录处于防爆破锁定期，带 `Retry-After` 响应头 |
| 500 | 服务端执行失败 |
| 503 | 依赖服务不可用（bot 未启动 / 数据库未连接 / 未配置令牌等） |

### 分页约定

列表类端点统一返回 `{ "total", "page", "limit", "items": [...] }`；查询参数 `page`（默认 1）、`limit`（默认值见各端点，上限 200）、`search`（模糊匹配）。

### WebSocket 关闭码

| 关闭码 | 含义 |
|---|---|
| 4401 | 会话令牌无效/过期，或未配置令牌 |
| 4450 | 沙盒未初始化（仅沙盒终端） |
| 4451 | 当前沙盒后端不支持终端（仅沙盒终端） |

---

## 登录（auth.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/login` | 用主令牌换取会话令牌。Body：`{ "token": "<主令牌>" }`。返回 `{status, session_token, expires_in}`（`expires_in` 为会话有效期秒数，默认 4 小时）。失败：401 令牌错误（附剩余尝试次数）/ 403 `block_weak_token` 且主令牌过弱 / 429 锁定期或连续失败达阈值（带 `Retry-After`）/ 503 未配置主令牌 |
| POST | `/api/logout` | 吊销当前会话令牌（需携带会话令牌）。返回 `{status: "ok"}` |
| POST | `/api/ws_ticket` | 为当前会话签发一次性 WebSocket 票据。返回 `{status, ticket, expires_in}`（默认 30 秒、单次使用）；会话失效 401 |

## 仪表盘（dashboard.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/status` | 运行状态：账号、当前模型/供应商、连接类型、运行时长、各平台适配器启停状态、沙盒/MCP/RAG 是否启用 |
| GET | `/api/stats` | 统计概览：群数、用户数、消息总数、记忆总数、今日消息数、今日 token、24h 活跃上下文 |
| GET | `/api/stats/tokens` | 近 N 天 token 用量（按天聚合）。Query：`days`（默认 7，1–30）。返回 `{ items: [{date, total}] }` |
| GET | `/api/platforms` | 平台适配器实时状态列表。返回 `{ items: [{name, type, is_started, is_connected}] }`；平台管理器不可用时 503 |

## 数据浏览（data.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/groups` | 群列表。Query：`page`、`limit`（默认 20）、`search`（群号/群名）。items：`{group_id, group_name}` |
| GET | `/api/users` | 用户列表（含权限）。Query：`page`、`limit`（默认 20）、`search`（QQ 号/昵称）。items：`{user_id, nickname, last_updated, permission_type, is_root}` |
| GET | `/api/messages` | 消息记录（按时间倒序）。Query：`page`、`limit`（默认 50）、`group_id`、`user_id`、`search`（内容模糊）。items：`{sole_id, message_id, user_id, group_id, time, time_str, message_content, nickname}` |
| PUT | `/api/users/{user_id}/permission` | 用户权限操作。Body：`{ "action": "promote" \| "demote" \| "blacklist" \| "unblacklist" }`。返回 `{status, role}` |

## 长期记忆（memory.py）

记忆类别枚举：`preference / fact / experience / emotion / group_topic / knowledge / domain / guideline`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/memory` | 记忆列表（倒序）。Query：`page`、`limit`（默认 20）、`category`、`user_id`、`search`（event 模糊）。items：`{memory_id, user_id, group_id, event_time, event_time_str, event, category, importance, credibility, access_count}` |
| DELETE | `/api/memory/{memory_id}` | 删除单条记忆（404 = 不存在） |
| POST | `/api/memory/batch_delete` | 批量删除。Body：`{ "ids": [1, 2, ...] }`。返回 `{status, deleted}`（实际删除数） |
| PUT | `/api/memory/{memory_id}` | 修改记忆字段。Body（均可选）：`{event, category, importance, credibility}` |

## 命令与工具（tools.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/commands` | 命令注册表元数据：名称、描述、别名、权限等级、冷却、用法、示例、参数定义 |
| GET | `/api/tools` | LLM 工具清单（本地 + MCP）。返回 `{available, tools, mcp_servers, sandbox_tools}`。单个 tool：`{name, description, parameters(JSON Schema), active, concurrent, background, chat_scope, source(local/mcp), mcp_server, source_detail, testable, testable_reason, presets}`；`sandbox_tools` 汇总沙盒依赖工具的环境事实与启用状态 `{names, facts, active, work_dir}` |
| POST | `/api/tools/test` | 面板内试运行工具（60 秒超时）。Body：`{ "name": "...", "arguments": {...} }`。返回 `{ok, result, duration_ms}` 或 `{ok: false, error, duration_ms}`。依赖聊天上下文（message_data）的本地工具不可测，`testable=false` |
| POST | `/api/tools/refresh` | 重跑各工具的动态 `tool_json`（沙盒环境描述/启用状态）并重建 schema 缓存。返回 `{status: "refreshed", changed_tools}`；ToolCalls 未就绪时 503 |

## 数据库控制台（database.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/db/status` | 连接状态：PG 版本、库名、库大小、启动时长、连接数、连接池信息、host/port/user（不含密码）。不可用时 `{available: false, reason}` |
| GET | `/api/db/tables` | public 下所有表：行数估计、大小、列数、注释（按大小倒序） |
| GET | `/api/db/table` | 单表结构。Query：`name`（表名，白名单正则校验）。返回列 / 索引 / 约束 / 精确行数 |
| POST | `/api/db/query` | 执行 SQL。Body：`{ "sql": "..." }`（上限 100k 字符）。返回结果集的语句（select/show/explain/values/table/with 或含 RETURNING）返回 `{ok, kind:"rows", columns, rows, row_count, truncated, duration_ms}`（最多 500 行，超长文本截断）；写语句返回 `{ok, kind:"status", status, duration_ms}`。失败返回 `{ok: false, error}`。单条 30 秒超时。每次执行写审计日志（日志器 `atri-bot.WebPanelDB`）；`web_panel.db_console_readonly` 为 `true` 时非查询语句 403 |

## 配置管理（config.py）

三个配置文件的读写接口形态一致：GET 返回 `{content, path, valid, masked}`，POST 保存前先备份为 `*.bak` 并返回 `{status, needs_restart: true, backup}`（`needs_restart` 为真表示需**手动**重启 bot 进程才能生效，面板不提供自动重启）。

> **密钥打码（默认开启）**：`web_panel.mask_secrets` 不为 `false` 时，GET 会把敏感值替换为哨兵 `"__KEEP__"`——主配置的 `web_panel.access_token`、`database.password`、`platforms.*.access_token`；供应商配置的 `api_key`（单值或号池数组）；MCP 配置的 `mcpServers.*.env.*` 值。POST 保存时哨兵自动还原为磁盘旧值（按供应商 name / MCP 服务名匹配），因此"只改其他字段"不会弄丢密钥；若填了哨兵却无旧值可还原，返回 400 而非写入半套密钥。想直接看/改真实密钥可把该开关设为 `false`（不建议）。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/config` | 读取主配置 config.json |
| POST | `/api/config` | 保存主配置。Body：`{ "content": "<json 文本>" }`。保存前做结构校验（platforms / account / root_user_id / database） |
| GET | `/api/supplier_config` | 读取供应商配置，额外返回解析好的 `suppliers: [{name, base_url, models: {模型名: {visual_sense, audio_sense, video_sense, document_sense}}}]` |
| POST | `/api/supplier_config` | 保存供应商配置（校验 api 数组与 name/base_url/api_key） |
| GET | `/api/mcp_config` | 读取 MCP 配置（文件不存在时返回默认 `{ "mcpServers": {} }` 模板，`exists: false`） |
| POST | `/api/mcp_config` | 保存 MCP 配置（仅校验 JSON 合法性） |
| POST | `/api/config/rollback` | 回滚到 `.bak` 备份。Body：`{ "target": "config" \| "supplier" \| "mcp" }`。实现为"当前 ↔ 备份"互换，可再次调用撤销。无备份时 404 |

## 人设管理（personas.py）

人设为配置目录 `chat_manager` 下的 `*.txt` 文件；人设名（key）只允许中文、字母、数字、`-`、`_`、`.`、空格。保存/删除均自动备份 `.bak`，并热刷新内存中的人设列表。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/personas` | 人设列表。items：`{key, size, mtime, is_default}`；附当前默认人设 `default` |
| GET | `/api/personas/{key}` | 读取人设内容。返回 `{key, content}` |
| PUT | `/api/personas/{key}` | 覆盖保存人设。Body：`{ "content": "..." }`。返回 `{status, refreshed}`（是否成功热刷新进 ChatManager） |
| POST | `/api/personas` | 新建人设。Body：`{ "key": "...", "content": "" }`。已存在时 400 |
| DELETE | `/api/personas/{key}` | 删除人设。默认人设不可删（400），先切换默认 |
| POST | `/api/personas/default` | 切换默认人设（写回 config.json 的 `ai_chat.playRole`）。Body：`{ "key": "..." }` |

## 适配器接口调用（message.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/message/call` | 通过平台适配器 `call_api` 调用任意平台端点（如 OneBot 的 `send_group_msg`），返回原始 JSON。Body：`{ "platform": "适配器名", "action": "端点名", "params": {...} }`。返回 `{status: "ok"/"error", result, duration_ms}`。30 秒超时。错误也走 200 + `status:"error"`（适配器不存在 / 超时 / 调用异常） |

---

## 聊天（chat.py + chat_engine.py）

### HTTP 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/chat/info` | 聊天页启动信息：`defaults`（supplier/model/persona/chat_parameter）、`webui_preset`（工具预设 default/deferred 名单）、`limits`（image/audio/video/file 上传限额，字节）、`max_turns`、`id_range` |
| POST | `/api/chat/upload` | 上传聊天附件（multipart `file` 字段，流式读取，按类别限大小）。返回 `{status, file}`（附件摘要，含 `id`）；超限 413 |
| GET | `/api/chat/files/{file_id}` | 附件预览/下载（会话令牌走 query 参数鉴权）。不存在或已过期 404 |
| GET | `/api/chat/avatar` | 机器人头像（会话令牌走 query 参数鉴权）：配置目录下的 ATRI-bot 图（png/jpg/jpeg/webp/gif） |
| GET | `/api/panel/logo` | 面板品牌图。**免鉴权**（登录页与 favicon 用）；文件不存在 404 |
| POST | `/api/chat/tools` | 保存 webui 工具预设。Body：`{ "tools": ["工具名"...], "deferred": ["工具名"...] \| 省略 }`。`deferred` 缺省表示不改动待发现组。持久化到 config.json。返回 `{status, tools, deferred}` |
| GET | `/api/chat/sessions` | 全部会话概览。返回 `{ items: [...] }` |
| DELETE | `/api/chat/sessions/{session_id}` | 删除会话。返回 `{status, deleted}` |

### WebSocket `/api/ws/chat`

鉴权：`?ticket=<一次性票据>`（先 `POST /api/ws_ticket` 获取），旧 `?token=<会话令牌>` 兼容。

客户端 → 服务端（JSON 消息）：

| type | 字段 | 说明 |
|---|---|---|
| `ping` | — | 心跳，回 `pong` |
| `load` | `session` | 加载指定会话并订阅其事件，回 `history` |
| `create` | — | 新建会话，回 `session` + `history` |
| `send` | `text`、`files`（附件 id 数组）、`settings`、`nonce`、`session?` | 发送消息；`session` 缺省则新建会话。会话忙时回 `busy` |
| `edit` | `um_index`、`text`、`resend`、`settings`、`session?` | 编辑第 um_index 条用户消息并截断后续（resend=true 时立即重发） |
| `stop` | — | 中止当前会话的生成，回 `stopping` |

服务端 → 客户端：

| type | 字段 | 说明 |
|---|---|---|
| `ready` | — | 连接就绪（首条消息） |
| `pong` | — | 心跳应答 |
| `session` | `id` | 会话已创建/切换 |
| `history` | `session`、`items`（时间线）、`running`、`persona` | 当前会话完整时间线 |
| `user_message` | 用户消息对象 | 新用户消息入时间线（广播） |
| `event` | `event` | Agent 流式事件（文本增量、工具调用等，源自 SubAgentRunner） |
| `done` | — | 一轮生成结束（含 usage 等） |
| `assistant_note` | `text` | 过程提示（如工具执行摘要） |
| `attachment` | `file` | 附件摘要（广播） |
| `merge_text` | `source`、`message` | 文本合并提示 |
| `busy` | `session` | 会话正在生成，请求被拒 |
| `stopping` | `session` | 已发出中止 |
| `error` | `message` | 请求错误（未知 type / 非法参数 / 消息为空等） |
| `deleted` | `session` | 会话已被删除（广播） |

---

## 系统控制（system.py）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/system/stop` | 请求主进程以 Ctrl+C 语义优雅关闭（回收沙盒 / MCP / 数据库连接池 / 插件等资源）后退出。返回 `{status: "stopping"}`。不可撤销，关闭后需**手动**重新启动（面板不提供自动重启，旧 `/api/system/restart` 已移除，请求会得到 404） |

### WebSocket `/api/ws/logs`

鉴权：`?ticket=<一次性票据>`（旧 `?token=` 兼容）。

连接成功后先推 `{"type": "history", "items": [...]}`（环形缓冲最近 500 条），之后每 0.25 秒批量推送 `{"type": "logs", "items": [...]}`。

单条日志：`{seq, time, level, name, message}`。

## 终端（terminal.py）— 主机 Shell

在 bot 所在主机上执行命令。**拿到有效会话即等于拿到主机权限**；所有从面板执行的命令都会写入审计日志（日志器 `atri-bot.Terminal`）。

### WebSocket `/api/ws/terminal`

鉴权：`?ticket=<一次性票据>`（旧 `?token=` 兼容）。

连接成功后服务端推 hello：

```json
{ "type": "hello", "platform": "win32", "isWindows": true, "cwd": "...", "home": "...",
  "user": "...", "host": "...", "sep": "\\", "commands": ["可用命令名", "..."] }
```

客户端 → 服务端：

| type | 字段 | 说明 |
|---|---|---|
| `exec` | `cmd` | 执行命令（≤8192 字符；同一连接同时只跑一条，忙时回 output 提示）。Windows 下支持裸盘符切换（如 `D:`） |
| `kill` | — | 终止正在运行的命令 |
| `ping` | — | 回 `pong` |
| `complete` | `id`、`frag`、`dir?`、`first?` | Tab 补全。`first=true` 补全命令名（扫描 PATH，上限 100 条）；否则补全 `dir` 目录下的文件名（隐藏文件需显式输入 `.` 前缀，上限 100 条，目录优先） |

服务端 → 客户端：

| type | 字段 | 说明 |
|---|---|---|
| `output` | `data` | 命令输出流（增量文本） |
| `exit` | `code`、`ms`、`cwd` | 命令结束：退出码、耗时毫秒、会话新工作目录（cd 会持久） |
| `complete` | `id`、`items: [{name, dir}]` | 补全结果 |
| `pong` | — | 心跳应答 |

单条命令最长运行 600 秒；连接关闭时自动终止仍在运行的命令。

## 沙盒（sandbox.py）

面板只依赖 `SandBoxBase` 的 panel_* 扩展点，不感知具体后端（docker / no-sandbox / e2b…）。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/sandbox/status` | `{configured, type, capabilities, backend, display, running, rows}`；沙盒未注册时只有前两项。`rows` 为状态展示行 |
| POST | `/api/sandbox/start` | 启动沙盒（bot 启动时初始化失败的场景下面板可懒启动并注册进容器）。返回 `{status: "started"/"already_running", backend}`；成功后自动刷新沙盒依赖工具的启用状态/描述 |
| POST | `/api/sandbox/stop` | 停止沙盒。返回 `{status: "stopped"/"already_stopped"}`；未初始化 503；成功后自动刷新沙盒依赖工具 |
| POST | `/api/sandbox/restart` | 重启沙盒。返回 `{status: "restarted", backend}`；成功后自动刷新沙盒依赖工具 |
| POST | `/api/sandbox/refresh-tools` | 按当前 `config.json` 的 `sand_box` 段重建沙盒（原先运行中则启动新实例），并刷新沙盒依赖工具的 `active` 与描述。返回 `{status: "refreshed", backend, running, changed_tools}` |

### WebSocket `/api/ws/sandbox-terminal`

协议与主机终端一致（hello / exec / kill / ping / output / exit / pong）；鉴权同 `/api/ws/terminal`。差异：

- `complete` 目前返回空 `items`（容器内文件系统补全未适配，保留协议应答）。
- 沙盒未初始化关闭码 4450；后端不支持终端关闭码 4451。
- hello 为 `{"type": "hello", "commands": [], ...sb.panel_terminal_info()}`（含 `cwd` 等）。

---

## 页面与静态资源（panel_router.py）

| 路径 | 说明 |
|---|---|
| `GET /admin/` | 面板单页（templates/index.html），`Cache-Control: no-store` |
| `/admin/static/*` | 静态 JS/CSS，同样强制 no-store，改动后普通刷新即可生效 |
| 安全头 | 全部 `/admin*` 响应：`X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: no-referrer`、CSP（`script-src 'self'`、`frame-ancestors 'none'` 等）；`/admin/api/*` 额外 `Cache-Control: no-store` |

## 路由 → 源文件速查

| 源文件 | 前缀 |
|---|---|
| `routes/dashboard.py` | `/api/status`、`/api/stats*`、`/api/platforms` |
| `routes/data.py` | `/api/groups`、`/api/users*`、`/api/messages` |
| `routes/memory.py` | `/api/memory*` |
| `routes/tools.py` | `/api/commands`、`/api/tools*` |
| `routes/database.py` | `/api/db/*` |
| `routes/config.py` | `/api/config*`、`/api/supplier_config*`、`/api/mcp_config*` |
| `routes/personas.py` | `/api/personas*` |
| `routes/message.py` | `/api/message/call` |
| `routes/chat.py` | `/api/chat/*`、`/api/panel/logo`、`/api/ws/chat` |
| `routes/system.py` | `/api/system/*`、`/api/ws/logs` |
| `routes/terminal.py` | `/api/ws/terminal` |
| `routes/sandbox.py` | `/api/sandbox/*`、`/api/ws/sandbox-terminal` |
