# QQ 官方机器人适配器（qqbot）

ATRI 内置的 `qqbot` 适配器直接对接 **QQ 开放平台机器人 API v2**（AppID / AppSecret），
不依赖 NapCat / SnowLuma 等第三方端，适合官方审核通过、可直接添加到群或私聊的机器人。

- 连接方式：WebSocket 网关（长连接，无需公网回调地址）
- 支持会话：QQ 群聊（**仅 @ 机器人**的消息）、C2C 单聊
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
| `intents` | 事件订阅位掩码，默认 `1 << 25`（群 @ + C2C + 机器人入群/退群等） |
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
| 群消息 | 全部群消息 | **只有 @ 机器人的消息** |
| 主动发消息 | 无限制 | 被动回复优先；主动消息有官方配额 |
| 被动回复 | 不需要 | 必须带 `msg_id`，5 分钟内有效，同一条消息次数有限 |
| 群成员查询 | 支持 | 不支持 |
| 禁言 / 戳一戳 / 贴表情 | 支持 | 不支持（安全 no-op） |
| 合并转发 | 支持 | 不支持（自动降级为分片文本） |
| 富媒体 | 直接发 URL / 路径 | 先上传（URL 或 base64），再以 `msg_type=7` 发送 |
| 群号 | 真实群号 | `group_openid`（映射成整数） |

由于群聊只能收到 @ 消息，`initiative_chat`（主动聊天）与基于全量群消息的话题提取在
`qqbot` 平台上的语义与 NapCat 不同，建议对官方群关闭主动聊天。

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
| 网关连接后收不到消息 | 机器人是否已被添加到群 / 是否在沙箱名单；群消息必须 @ 机器人 |
| 发送返回 400 且提示 `msg_id` 无效 | 被动回复已超过 5 分钟或次数用尽，可开启 `allow_proactive` 或等待用户新消息 |
| 发送图片失败 | 检查本地文件路径是否存在；远程 URL 是否可被公网访问 |
| 日志里群 ID 与真实群号不一致 | 这是 openid 哈希映射，用日志中的 openid + `id_map` 固定映射即可 |

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

然后在群里 @ 机器人，或在沙箱名单内私聊机器人即可触发回复。
