# 面板安全说明（威胁模型 / 加固清单 / 部署 / 复测）

管理面板与 bot **同进程**运行，默认监听 `127.0.0.1`。**持有面板登录口令等价于持有主机权限**——终端、沙盒终端、SQL 控制台、工具试运行、平台接口调用都在同一条鉴权边界之内，请按"等同 SSH 凭据"的标准保管。

## 信任边界

| 层级 | 凭证 | 存储 / 传递 |
|---|---|---|
| 主令牌（面板口令） | `web_panel.access_token` 或 `ATRI_PANEL_TOKEN` | 仅用于 `POST /api/login` 换会话令牌，不出现在其他端点 |
| 会话令牌 | `POST /api/login` 签发 | 内存态、只存 SHA-256 摘要；HTTP 走 `Authorization: Bearer`，`<img>`/`<audio>` 预览走 `?token=` |
| WS 票据 | `POST /api/ws_ticket` 签发 | 30 秒有效、单次使用；WebSocket 只带 `?ticket=`，不再把长期会话令牌放进 URL |

## 加固清单

| 项 | 说明 |
|---|---|
| 认证链 | 主令牌仅登录可用；常量时间比较；弱口令可硬拒（`block_weak_token`） |
| 会话 | 固定 1-24h（默认 4h）、不滑动；登出/过期/主令牌轮换即失效；容量上限 100 |
| WebSocket | 一次性票据（30s、单次）；建连后周期复验，吊销后 4401 断开；旧 `?token=` 兼容 |
| 安全响应头 | 全部 `/admin*`：`nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy: no-referrer`、CSP（`script-src 'self'`、`frame-ancestors 'none'` 等）；`/admin/api/*` 加 `Cache-Control: no-store` |
| CSP 前提 | `index.html` 不含内联脚本（主题引导在 `static/js/theme-init.js`）；新增内联脚本会导致被 CSP 拦截 |
| 附件 | 落盘名 = 随机 id + 净化扩展名；MIME 由服务端白名单推导（**不信任客户端 content_type**）；下载强制 attachment + `nosniff` + `CSP: default-src 'none'` |
| 配置接口 | 密钥打码为 `__KEEP__`（`mask_secrets` 默认开）：面板口令 / 平台 token / DB 密码 / 供应商 api_key / MCP env；保存时按旧值还原 |
| SQL 控制台 | 每次执行写审计日志（`atri-bot.WebPanelDB`）；可选只读模式 `db_console_readonly` |
| 终端 | 每条命令写审计日志（`atri-bot.Terminal`） |
| 敏感响应 | `/admin/api/*` 全量 no-store，不落浏览器/代理缓存 |

## 配置开关（`config.json` → `web_panel`）

| 键 | 默认 | 说明 |
|---|---|---|
| `access_token` | — | 面板口令；**必须 16 字符以上随机值**（推荐 `python -c "import secrets; print(secrets.token_urlsafe(32))"`） |
| `block_weak_token` | `false` | `true` 时弱口令（<16 字符或与平台 token 相同）直接拒绝登录（403） |
| `session_ttl_hours` | `4` | 会话有效期，钳制 1-24 |
| `mask_secrets` | （视为 `true`） | 为 `false` 时配置接口回吐真实密钥（不建议） |
| `db_console_readonly` | `false` | `true` 时 SQL 控制台仅允许查询语句 |
| `host` / `port` | `127.0.0.1` / `5125` | 环境变量 `ATRI_WEB_PANEL_HOST` / `ATRI_WEB_PANEL_PORT` 优先 |
| `enable` | `true` | 为 `false` 时不启动面板 |

补充环境变量：`ATRI_PANEL_TOKEN`（主令牌兜底来源，优先级低于 `access_token`）。

## 部署建议（Docker + 反向代理）

- 保持面板只绑本机：compose 里 `ATRI_WEB_PANEL_HOST=0.0.0.0` 仅供容器内，宿主机映射默认 `127.0.0.1:5308:5308`，**不要把 `0.0.0.0` 直接映射到公网**。
- 远程访问必须经反向代理 + HTTPS（WSS）。nginx 参考：

```nginx
location /admin/ {
    proxy_pass http://127.0.0.1:5308;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;   # WebSocket（日志/终端/聊天）
    proxy_set_header Connection "upgrade";
}

# 访问日志脱敏：不要使用包含 $request_uri 的格式，
# 面板的图片/音频预览会带 ?token=、WebSocket 会带 ?ticket=，避免凭证进日志
log_format atri_panel '$remote_addr - [$time_local] "$request_method $uri" $status $body_bytes_sent';
access_log /var/log/nginx/atri-panel.log atri_panel;
```

- 可在反代层再加一道保护：IP 白名单、HTTP Basic、限速（`limit_req`），与面板自身的登录锁定形成纵深。

## 登录锁定（有意保留的取舍）

- 全局统一计数（不区分 IP）：连续失败 3 次即锁定，时长 `10min × 2^(失败次数-3)`，封顶 24h；锁定期内**正确口令也 429**；解锁方式：重启 bot 进程（计数为内存态）。
- 这意味着任何能访问面板端口的人都能把登录"锁在门外"（可用性 DoS）。缓解：面板只绑回环 + 反代层限速/IP 白名单；已有会话不受锁定影响。
- 该行为是刻意选择（防爆破优先），改动前请评估。

## 复测清单（自动化 + 手动渗透用例）

自动化：

```bash
uv run python -m pytest tests/test_web_panel_security.py tests/test_web_panel_auth.py -q
```

手动（dev：`uv run python -m atribot.web_panel.dev_server`，令牌 `dev-token`）：

| # | 用例 | 预期 |
|---|---|---|
| 1 | `/admin/api/status` 不带 `Authorization` | 401；未配置令牌时 503 |
| 2 | `curl -sI http://127.0.0.1:5125/admin/` | 含 `X-Frame-Options: DENY`、`Content-Security-Policy`、`Referrer-Policy: no-referrer` |
| 3 | 同一张 `ws_ticket` 连续用两次 | 第二次以 4401 关闭 |
| 4 | 登出后观察已建立的 WS | 数秒内 4401 断开 |
| 5 | 上传 `evil.html`（Content-Type `text/html`）并请求 `/admin/api/chat/files/{id}` | `Content-Disposition: attachment`、`nosniff`，响应 MIME 非 `text/html` |
| 6 | 消息记录/记忆/日志/工具结果/终端输出塞 `<img src=x onerror=alert(1)>`、`"><svg/onload=alert(1)>` | 只显示为文本；浏览器 Console 无 CSP 报错、无弹窗 |
| 7 | `<iframe src="http://127.0.0.1:5125/admin/">` | 被 `X-Frame-Options` / CSP `frame-ancestors` 拒绝 |
| 8 | `GET /admin/api/config` | `web_panel.access_token` 显示为 `__KEEP__`；改无关字段保存后口令未丢 |
| 9 | 执行任意 SQL 后看日志 | 出现 `atri-bot.WebPanelDB` 审计行（含来源 IP 与 SQL 摘要） |
| 10 | 连续 3 次错误口令 | 429 + `Retry-After`（预期行为，见上节） |
| 11 | 上传文件名含 `:`、`<`、路径分隔符 | 落盘名扩展名只剩字母数字，无异常路径 |

## 已知取舍 / 未做项

- 登录锁定 DoS：保持现状（见上）。
- 图片/音频预览仍用 `?token=`（HTML 标签限制）；已用 `Referrer-Policy: no-referrer` 缓解，反代须按上文脱敏日志。
- 待办（P2）：上传频率/总量限制与定时清理、根日志 DEBUG 卫生、请求体大小上限、WS 连接数上限。
- 依赖漏洞扫描（可选）：`uv run bandit -r atribot/web_panel`、`uv run pip-audit`（需先安装并联网）。
