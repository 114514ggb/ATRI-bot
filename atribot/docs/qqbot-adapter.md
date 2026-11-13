# QQ 官方机器人适配器（qqbot）

ATRI 内置的 `qqbot` 适配器直接对接 **QQ 开放平台机器人 API v2**（AppID / AppSecret），
不依赖 NapCat / SnowLuma 等第三方端，适合官方审核通过、可直接添加到群或私聊的机器人。

- 连接方式：WebSocket 网关（长连接，无需公网回调地址）
- 支持会话：QQ 群聊（@ 机器人的消息 + 平台下发的**全量群消息** `GROUP_MESSAGE_CREATE`）、C2C 单聊
- 代码位置：`atribot/core/platform/qqbot/`

## 1. 在 QQ 开放平台准备机器人

1. 打开 <https://q.qq.com/> 注册并创建机器人，进入「开发设置」拿到 `AppID` 与 `AppSecret`。
2. 在「开发设置 → 沙箱配置」把机器人添加到测试群 / 测试用户（沙箱环境）。
3. 确保机器人具备「群聊 @ 消息」「单聊消息」相关权限；正式环境需要提审上线。
4. 把 `AppID` / `AppSecret` 填入 `assets/config.json` 的 `platforms.qqbot`。

> 注意：`AppSecret` 属于敏感凭据，不要提交到公开仓库。

## 2. 配置示例

```json
{
  "platforms": {
    "napcat": { "...": "原有 OneBot 配置" },
    "qqbot": {
      "adapter": "qqbot",
      "connection_type": "qqbot",
      "app_id": "你的 AppID",
      "app_secret": "你的 AppSecret",
      "sandbox": false,
      "text_chunk_size": 1500,
      "max_passive_replies": 5,
      "allow_proactive": false,
      "id_map": {
        "group": {},
        "user": {}
      },
      "enabled": true
    }
  }
}
```

| 字段 | 说明 |
|---|---|
| `adapter` | 固定 `qqbot` |
| `connection_type` | 固定 `qqbot` |
| `app_id` / `app_secret` | 开放平台凭据（必填） |
| `sandbox` | `true` 时使用 `sandbox.api.sgroup.qq.com` |
| `intents` | 事件订阅位掩码，默认 `1 << 25`（群 @ + C2C + 机器人入群/退群等）；需要接收全量群消息时加上 `1 << 26`（如 `100663296`），并确认机器人已开通「群消息」权限 |
| `text_chunk_size` | 单条文本最大字符数，超出自动分片（默认 1500） |
| `max_passive_replies` | 同一条入站消息最多被动回复次数（官方上限 5） |
| `allow_proactive` | 无被动回复目标时是否允许主动消息（受官方配额限制，默认关闭） |
| `id_map` | openid → 整数 ID 的手工映射（见下文） |
| `source_name` | 来源标识，默认取平台条目 key |
| `enabled` | 是否启用 |

> Web 管理面板「平台连接」页可直接把连接方式切换为 `qqbot` 并填写 AppID / AppSecret；
> Docker 部署也可用 `ATRI_PLATFORM_<平台名>_APP_ID` / `_APP_SECRET` / `_SANDBOX` 等环境变量覆盖。

## 3. openid 与整数 ID

官方接口里的 `group_openid` / `user_openid` 是字符串，而 ATRI 的数据库、白名单、
上下文缓存全部使用整数 ID。适配器会做**稳定哈希映射**：

- 结果落在 `2^62 ~ 2^63` 区间（最高位固定为 1），不会与真实 QQ 号冲突
- 只由 openid 决定，重启后不变，无需额外持久化
- 首次见到某个群 / 用户时，日志会打印映射关系，例如：

```
QQ 官方机器人 ID 映射: 群 openid=ABCDEF... -> 4611686018427387904
```

需要固定 ID（例如想让群 ID 与真实群号一致）时，可在 `id_map` 中手工指定：

```json
"id_map": {
  "group": { "ABCDEF...": 123456789 },
  "user":  { "XYZ...": 10001 }
}
```

> `id_map` 属于高级字段，Web 管理面板的表单不含该项，请直接编辑 `assets/config.json`。

## 4. 白名单配置

白名单同时支持整数 ID 与原始 openid 字符串：

```json
{
  "group_white_list": [123456789, "ABCDEF...-group-openid"],
  "private_chat_white_list": [10001, "XYZ...-user-openid"],
  "root_user_id": "XYZ...-user-openid"
}
```

- 群白名单：`group_white_list` 命中整数群 ID 或 `group_openid` 均可
- 私聊白名单：`private_chat_white_list` 命中整数用户 ID 或 `user_openid` 均可
- `root_user_id` 同样支持 openid，用于绕过白名单

> 推荐先用整数 ID（从启动日志或 `id_map` 获取），openid 字符串主要用于排障和应急。

## 5. 与 NapCat / OneBot 的能力差异

| 能力 | OneBot（NapCat） | QQ 官方机器人 |
|---|---|---|
| 群消息 | 全部群消息 | @ 机器人的消息；平台下发全量群消息（`GROUP_MESSAGE_CREATE`）时同样会处理 |
| 主动发消息 | 无限制 | 被动回复优先；主动消息有官方配额 |
| 被动回复 | 不需要 | 必须带 `msg_id`，5 分钟内有效，同一条消息次数有限 |
| 群成员查询 | 支持 | 不支持 |
| 禁言 / 戳一戳 / 贴表情 | 支持 | 不支持（安全 no-op） |
| 合并转发 | 支持 | 不支持（自动降级为分片文本） |
| 富媒体 | 直接发 URL / 路径 | 先上传（URL 或 base64），再以 `msg_type=7` 发送 |
| 群号 | 真实群号 | `group_openid`（映射成整数） |

全量群消息事件（`GROUP_MESSAGE_CREATE`）经 `translate.py` 翻译为普通群消息事件后进入同一
条消息流水线，`is_at` 判定方式：

- `GROUP_AT_MESSAGE_CREATE`：收到即视为被 @
- `GROUP_MESSAGE_CREATE`：按正文中的 `<@openid>` 提及标记与事件的 `mentions[].is_you` /
  机器人自身 openid 判断；未被 @ 的普通群消息 `is_at=False`，交给 `initiativeChat`
  （关键词 / 随机触发 / 追问检测）决定是否发言

> `GROUP_AT_MESSAGE_CREATE` 与 `GROUP_MESSAGE_CREATE` 可能推送同一条消息，适配器按官方
> 消息 ID 去重（缓存最近 512 条）；若先到的全量群消息未被识别为 @，后到的 @ 事件仍会补投。
> 其他机器人发送的消息会被忽略，避免机器人之间互相触发。
> 未开通全量群消息权限时，群聊仍只能收到 @ 消息，`initiative_chat` 的语义与 NapCat 不同，
> 建议对官方群关闭主动聊天。

## 6. 发送行为说明

- **文本**：CQ 码会被解析成文本 + 媒体；文本按 `text_chunk_size` 分片
- **被动回复**：优先使用 `reply` 段里的消息 ID；否则复用该会话 5 分钟内最近一条入站
  消息的 `msg_id`，`msg_seq` 自增；超过 `max_passive_replies` 次后不再回复
- **主动消息**：没有可用被动目标时，`allow_proactive=false` 直接丢弃并记录 WARNING；
  开启后会尝试主动发送（可能因官方配额失败）
- **图片 / 视频 / 语音 / 文件**：网络资源交给官方接口按 URL 拉取；本地文件读取后以
  base64 `file_data` 上传。语音请优先使用平台可识别的格式（silk），失败会记录 WARNING
- **合并转发**：`send_group_merge_text` / `send_group_merge_forward` 降级为普通文本

## 7. 排障

| 现象 | 排查方向 |
|---|---|
| 启动日志出现「缺少 app_id / app_secret」 | 检查 `platforms.qqbot` 是否填写凭据、`enabled` 是否为 `true` |
| 401 / `access token` 相关错误 | 核对 AppSecret 是否复制完整；token 过期会自动刷新，持续失败需检查开放平台机器人状态 |
| 网关连接后收不到消息 | 机器人是否已被添加到群 / 是否在沙箱名单；群消息需 @ 机器人，或机器人开通「群消息」权限后由平台下发 `GROUP_MESSAGE_CREATE` |
| 日志出现「忽略未处理的 QQ 官方事件」 | 该事件类型未被适配器翻译（如频道 / 互动事件）；`GROUP_MESSAGE_CREATE` 已支持，若仍出现请确认运行的是最新代码 |
| 发送返回 400 且提示 `msg_id` 无效 | 被动回复已超过 5 分钟或次数用尽，可开启 `allow_proactive` 或等待用户新消息 |
| 发送图片失败 | 检查本地文件路径是否存在；远程 URL 是否可被公网访问 |
| 日志里群 ID 与真实群号不一致 | 这是 openid 哈希映射，用日志中的 openid + `id_map` 固定映射即可 |
| 日志出现 `Could not contact DNS servers` | 默认已是系统 DNS；若仍失败，在顶层 `network` 段用 `dns_mode=custom` + `dns_nameservers` 指定 DNS |
| 需要走代理访问 openapi | 设置顶层 `network.proxy`；`proxy_bypass` 里的域名（如 `bots.qq.com`）仍直连 |

### DNS / 代理（顶层 `network` 段）

`aiohttp` 检测到已安装 `aiodns` 时默认使用 c-ares 解析。c-ares 在 Windows、VPN、
多网卡、WSL 环境下可能读不到可用的 nameserver，直接报
`Could not contact DNS servers`，表现为网关反复重连但永远失败。

所有 aiohttp 出口（QQ 官方机器人 auth/api/gateway、OneBot HTTP、`HTTPClient`、
LLM API）现统一走 `atribot/common_utils/net_utils.py` 的工厂，默认
`dns_mode=system`（系统 getaddrinfo，兼容性最好）。

`assets/config.json` 顶层可选项：

| 字段 | 默认 | 说明 |
|---|---|---|
| `dns_mode` | `system` | `system` 系统 DNS / `custom` 指定 DNS 服务器（aiodns）/ `cares` 沿用 aiohttp 默认 |
| `dns_nameservers` | `[]` | `dns_mode=custom` 时使用的 DNS 服务器，如 `["223.5.5.5", "119.29.29.29"]` |
| `proxy` | 空 | HTTP(S) 代理地址，留空表示直连 |
| `proxy_bypass` | qq 官方域名 + 本机 | 不走代理的主机（完全相等或域名后缀匹配） |
| `trust_env` | `false` | 是否让 aiohttp 读取环境变量中的代理配置 |
| `connect_timeout` / `total_timeout` | 10 / 30 | 建连 / 整体超时（秒） |
| `probe_hosts` | `bots.qq.com`、`api.sgroup.qq.com` | 启动期 DNS 自检探测的主机 |

- 启动时 `BotFramework._diagnose_network()` 会做一次自检（日志前缀 `atri-bot.Network`）；
  配置的模式失败时会自动尝试降级为系统 DNS，仍失败则打印配置建议（不阻断启动）
- 修改 `network` 段后：`HTTPClient` 立即重建连接池；QQ 官方网关、OneBot HTTP 会话、
  LLM API 客户端需要重启才重建 session
- Docker 部署可用 `ATRI_NETWORK_DNS_MODE`、`ATRI_NETWORK_DNS_NAMESERVERS`（逗号分隔）、
  `ATRI_NETWORK_PROXY`、`ATRI_NETWORK_TRUST_ENV` 覆盖

## 8. 运行与验证

```bash
# 单元测试（离线）
uv run python -m pytest tests/test_qqbot_adapter.py -q

# 启动机器人
uv run main.py
```

启动后日志应出现：

```
QQ 官方机器人已上线: <昵称> (<bot id>)
QQ 官方机器人连接已建立
```

然后在群里 @ 机器人，或在沙箱名单内私聊机器人即可触发回复；平台下发全量群消息
（`GROUP_MESSAGE_CREATE`）时，普通群消息同样会进入 `initiativeChat` 决策。
