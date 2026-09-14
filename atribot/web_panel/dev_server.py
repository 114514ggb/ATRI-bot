"""面板独立开发/调试服务器

用法:
    python -m atribot.web_panel.dev_server
    # 打开 http://127.0.0.1:8090/admin/ ，访问令牌: dev-token
"""

import asyncio
import json
import logging
import os
import random
import re
import sys
import tempfile
import time
from pathlib import Path

from atribot.core.command.command_parsing import Command, CommandSystem, ParamType

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEV_TOKEN = "dev-token"


def _prepare_files() -> Path:
    """在临时目录中生成一份隔离的配置）"""
    tmp = Path(tempfile.mkdtemp(prefix="atri_panel_dev_"))

    persona_dir = tmp / "personas"
    persona_dir.mkdir()
    (persona_dir / "ATRI_dev.txt").write_text(
        "你是 ATRI,高性能的开发区测试人设。", encoding="utf-8"
    )
    (persona_dir / "Neuro_dev.txt").write_text(
        "你是 Neuro,另一个开发区测试人设，病娇款。", encoding="utf-8"
    )

    config = {
        "platforms": {
            "napcat": {
                "adapter": "onebot",
                "connection_type": "WebSocket_client",
                "access_token": "dev-napcat-token",
                "url": "127.0.0.1:8888",
            }
        },
        "web_panel": {"enable": True, "access_token": DEV_TOKEN, "port": 8090},
        "account": {"id": 10000, "name": "ATRI-dev"},
        "root_user_id": 10001,
        "file_path": {
            "relative_to_root": {
                "chat_manager": str(persona_dir),
                "supplier_config_path": str(tmp / "supplier_config.json"),
                "mcp_config": str(tmp / "mcp_server.json"),
            }
        },
        "model": {
            "connect": {"supplier": "dev-supplier", "model_name": "dev-model", "user_global_context": True},
            "chat_parameter": {"temperature": 0.6, "top_p": 0.9, "max_tokens": 65536, "stream": False, "tool_choice": "auto"},
            "RAG": {"enable": True, "dimensions": 1024},
            "standby_model": [{"supplier": "dev-supplier", "model_name": "dev-model2"}],
        },
        "ai_chat": {"playRole": "ATRI_dev", "ai_max_record": 10, "group_max_record": 20, "private_max_record": 20},
        "sand_box": {"image": "atri-sandbox:latest"},
        "tool_presets": {
            "group_chat": {"default": ["web_search", "memory_search"], "deferred": ["run_python_code"]},
            "private_chat": ["web_search"],
            "agency_Agent": ["run_command"],
        },
        "group_white_list": [123456, 789012],
        "group_initiative_chat_white_list": [123456],
        "group_information_extraction": [],
        "private_chat_white_list": [10086],
        "database": {"host": "127.0.0.1", "port": 5432, "user": "postgres", "password": "dev"},
    }
    (tmp / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=4), encoding="utf-8")

    supplier = {
        "api": [
            {
                "name": "dev-supplier",
                "base_url": "http://localhost:9999/v1/chat/completions",
                "api_key": ["sk-dev-1", "sk-dev-2"],
                "models": {
                    "dev-model": {"visual_sense": True, "audio_sense": False, "video_sense": False},
                    "dev-model2": {},
                },
            }
        ]
    }
    (tmp / "supplier_config.json").write_text(json.dumps(supplier, ensure_ascii=False, indent=4), encoding="utf-8")
    (tmp / "mcp_server.json").write_text(json.dumps({"mcpServers": {}}, ensure_ascii=False, indent=4), encoding="utf-8")
    return tmp


class MockDatabase:
    """按 SQL 关键词返回假数据的最小数据库 mock"""

    _GROUPS = [
        {"group_id": 123456, "group_name": "ATRI 开发测试群"},
        {"group_id": 789012, "group_name": "摸鱼闲聊群"},
        {"group_id": 555777, "group_name": "技术交流群"},
    ]
    _USERS = [
        {"user_id": 10001, "nickname": "root 大人", "last_updated": "2026-09-13 10:00:00", "permission_type": None, "is_root": True},
        {"user_id": 10086, "nickname": "测试用户甲", "last_updated": "2026-09-13 09:30:00", "permission_type": "administrator", "is_root": False},
        {"user_id": 22222, "nickname": "路过的小明", "last_updated": "2026-09-12 22:10:00", "permission_type": None, "is_root": False},
        {"user_id": 33333, "nickname": "黑名单选手", "last_updated": "2026-09-11 08:00:00", "permission_type": "blacklist", "is_root": False},
    ]
    _MESSAGES = [
        {"sole_id": 100 - i, "message_id": 9000 + i, "user_id": 10086, "group_id": 123456, "time": time.time() - i * 90, "message_content": f"这是第 {i + 1} 条开发测试消息 [CQ:face,id=178]", "nickname": "测试用户甲"}
        for i in range(30)
    ]
    _MEMORIES = [
        {"memory_id": 50 - i, "user_id": 10086, "group_id": 123456, "event_time": time.time() - i * 3600, "event": f"用户喜欢在深夜听爵士乐（测试记忆 {i + 1}）", "category": ["fact", "preference", "emotion", "knowledge"][i % 4], "importance": random.randint(3, 9), "credibility": random.randint(4, 10), "access_count": random.randint(0, 20)}
        for i in range(12)
    ]

    async def execute_SQL(self, sql, args=None):
        s = " ".join(sql.lower().split())
        # LIKE 参数（搜索/筛选）在 mock 里做真过滤；$N 占位符按 args 顺序解析
        like = None
        eq_vals = []
        if args:
            for a in args:
                if isinstance(a, str) and a.startswith("%") and a.endswith("%"):
                    like = a[1:-1].lower()
                else:
                    eq_vals.append(a)
        if "count(*)" in s:
            return [{"c": len(self._rows_for(s, like, eq_vals))}]
        return [dict(r) for r in self._rows_for(s, like, eq_vals)]

    def _rows_for(self, s, like, eq_vals):
        """按 FROM 表名返回（含 LIKE 过滤、等值过滤、LIMIT/OFFSET 分页）的行集"""
        table = next((t for t in ("user_group", "users", "message", "atri_memory") if f"from {t}" in s), None)
        if table is None and "token_statistics" in s:
            if "group by" in s:  # 按天明细
                return [{"date": f"09-{7 + i}", "daily_total": 52800 - i * 6100} for i in range(7)]
            return [{"c": 52800}]  # 今日汇总
        if table is None:
            return []
        rows = list({
            "user_group": self._GROUPS,
            "users": self._USERS,
            "message": self._MESSAGES,
            "atri_memory": self._MEMORIES,
        }[table])
        if like:
            def hit(r):
                # 按表取匹配文本（if/elif 保证只访问该表行内存在的键）
                if table == "user_group":
                    text = f"{r['group_id']} {r['group_name']}"
                elif table == "users":
                    text = f"{r['user_id']} {r['nickname']}"
                elif table == "message":
                    text = r["message_content"]
                else:
                    text = r["event"]
                return like in text.lower()
            rows = [r for r in rows if hit(r)]
        if eq_vals:
            eq_cols = re.findall(r"(\w+)\s*=\s*\$\d+", s)
            for col, val in zip(eq_cols, eq_vals):
                rows = [r for r in rows if str(r.get(col)) == str(val)]
        m = re.search(r"limit (\d+) offset (\d+)", s)
        if m:
            limit, offset = int(m.group(1)), int(m.group(2))
            rows = rows[offset: offset + limit]
        return rows

    async def execute_with_pool(self, query, params=None, fetch_type="all"):
        """MemoryVectorStore 走此接口；DELETE/UPDATE 直接返回成功"""
        s = " ".join(query.lower().split())
        if s.startswith("delete"):
            return ({"memory_id": (params or [0])[0]},) if "returning" in s else None
        if s.startswith("update") and "returning" in s:
            return {"memory_id": (params or [0])[0]}
        return await self.execute_SQL(query, params)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _noop_handler():
    """面板只读取命令元数据，处理函数不会被调用"""


def _fake_command(name, description, params=(), aliases=(), authority_level=1, cooldown=0, examples=()):
    cmd = Command(
        name=name,
        handler=_noop_handler,
        description=description,
        aliases=list(aliases),
        authority_level=authority_level,
        cooldown=cooldown,
        examples=list(examples),
    )
    for p in params:
        cmd.add_param(**p)
    return cmd


class _FakeCommandSystem(CommandSystem):
    """预置覆盖各字段形态的假命令，使命令页在开发模式下可渲染（跳过父类构造的容器依赖）"""

    def __init__(self):
        commands = [
            _fake_command(
                name="help",
                description="显示帮助信息",
                aliases=["帮助"],
                authority_level=0,
                examples=["/help", "/help -l", "/help --list", "/help <命令名>"],
                params=[
                    dict(name="list", param_type=ParamType.FLAG, short_option="l", long_option="--list", description="显示支持的所有命令"),
                    dict(name="command_name", param_type=ParamType.POSITIONAL, description="要查看帮助的特定命令名", required=False, type=str),
                ],
            ),
            _fake_command(
                name="token",
                description="查询/统计 token 消耗",
                authority_level=2,
                cooldown=30,
                examples=["/token", "/token --days 7", "/token 10086 33333 --days 3 -v"],
                params=[
                    dict(name="days", param_type=ParamType.OPTION, short_option="d", long_option="--days", description="统计最近多少天", default=7, type=int, metavar="N"),
                    dict(name="sort", param_type=ParamType.OPTION, long_option="--sort", description="排序方式", default="time", choices=["time", "token"]),
                    dict(name="user_id", param_type=ParamType.POSITIONAL, description="目标用户 QQ 号（可多个，缺省为调用者）", required=False, type=int, metavar="QQ", multiple=True),
                    dict(name="verbose", param_type=ParamType.FLAG, short_option="v", long_option="--verbose", description="输出每日明细"),
                ],
            ),
            _fake_command(
                name="status",
                description="查看机器人运行状态",
                aliases=["状态"],
                authority_level=1,
                examples=["/status"],
            ),
        ]
        self.command_registry = {c.name: c for c in commands}
        self.alias_registry = {a: c.name for c in commands for a in c.aliases}


async def _fake_log_stream():
    """持续产生假日志，验证 WebSocket 日志流"""
    sources = ["PlatformManager", "atri-bot.ChatManager", "atri-bot.LLM", "OneBotWSClient", "atri-bot.Memory", "atri-bot.Whitelist", "websockets.client"]
    templates = [
        lambda: "收到群消息事件: group=123456",
        lambda: f"LLM 响应完成，耗时 {random.randint(10, 900)}ms",
        lambda: f"记忆检索命中 {random.randint(5, 500)} 条",
        "WebSocket 心跳正常",
        "工具调用 web_search 执行成功",
        "白名单校验通过: group=123456",
        '收到 OneBot 事件: {"post_type":"message","message_type":"group","sub_type":"normal","group_id":123456,"user_id":10086,"message":"[CQ:at,qq=10000] 早呀 ATRI，今天天气怎么样？顺便帮我看看这个链接 https://example.com/very/long/path/to/some/resource 太长了截断试试看效果","raw_message":"[CQ:at,qq=10000] 早呀 ATRI","font":0,"sender":{"user_id":10086,"nickname":"测试用户甲","card":"","sex":"unknown","age":0,"area":"","level":"","role":"member","title":""}} [1162 bytes]',
    ]
    counter = 0
    while True:
        counter += 1
        name = random.choice(sources)
        level = random.choice([logging.DEBUG] * 2 + [logging.INFO] * 5 + [logging.WARNING, logging.ERROR])
        if name == "websockets.client":
            # 模拟 websockets 库的帧日志（DEBUG，应被面板过滤）与少见 WARNING（应保留）
            level = logging.WARNING if random.random() < 0.15 else logging.DEBUG
        tpl = random.choice(templates)
        message = tpl() if callable(tpl) else tpl
        if name == "websockets.client":
            message = random.choice([
                "> PING ae 18 e8 98 [binary, 4 bytes]",
                "< PONG ae 18 e8 98 [binary, 4 bytes]",
                "% sent keepalive ping",
                "< TEXT '{\"time\":1789319514,\"self_id\":3930909243,\"post_t...true},\"interval\":30000}' [149 bytes]",
            ])
        logging.getLogger(name).log(level, f"#{counter} {message}")
        await asyncio.sleep(2)


def main() -> None:
    tmp = _prepare_files()
    os.environ["ATRI_CONFIG_PATH"] = str(tmp / "config.json")

    import uvicorn
    from fastapi import FastAPI

    from atribot.core.atri_config import atriConfig
    from atribot.core.command.async_permissions_management import PermissionsManagement
    from atribot.core.service_container import container
    from atribot.web_panel.panel_router import _ensure_log_handler, mount_static, router

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s | %(message)s")

    container.register("config", atriConfig())
    container.register("database", MockDatabase())
    container.register("PermissionsManagement", PermissionsManagement())
    container.register("CommandSystem", _FakeCommandSystem())

    app = FastAPI(title="ATRI Admin Panel (dev)")
    app.include_router(router)
    mount_static(app)

    @app.middleware("http")
    async def _no_cache_static(request, call_next):
        resp = await call_next(request)
        if request.url.path.startswith("/admin/static"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.on_event("startup")
    async def _start_fake_logs() -> None:
        _ensure_log_handler()
        asyncio.get_event_loop().create_task(_fake_log_stream())

    port = int(os.environ.get("ATRI_PANEL_PORT", "8090"))
    print(f"[dev_server] 临时配置目录: {tmp}")
    print(f"[dev_server] 面板地址: http://127.0.0.1:{port}/admin/  访问令牌: {DEV_TOKEN}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
