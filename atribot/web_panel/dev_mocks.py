"""面板开发/调试用的 mock 实现:数据库、命令系统、LLM 工具与假日志流

由 dev_server.py 在 main() 中注册进 DI 容器，仅服务于独立开发模式。
"""

import asyncio
import json
import logging
import random
import re
import time

from atribot.core.command.command_parsing import Command, CommandSystem, ParamType
from atribot.core.platform.manager import PlatformManager
from atribot.core.type.context_types import ToolSearchRequested
from atribot.LLMchat.MCP.tool_model import LocalTool, MCPTool


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

    # 数据库页（/api/db/*）的罐头 pg_catalog 数据，结构与真实查询一致
    _TABLE_SIZES = [
        # table_name, 行数估计, size_bytes, size_pretty, 列数, 注释
        ("message", 128450, 96374528, "92 MB", 6, "聊天消息记录"),
        ("atri_memory", 3821, 41582550, "40 MB", 11, "长期记忆（含 pgvector 向量）"),
        ("token_statistics", 55210, 12582912, "12 MB", 8, "LLM token 消耗统计"),
        ("chat_context", 86, 4194304, "4096 kB", 7, "会话上下文"),
        ("users", 612, 278528, "272 kB", 3, "用户昵称表"),
        ("user_group", 35, 131072, "128 kB", 2, "群组表"),
        ("user_info", 428, 98304, "96 kB", 3, "用户画像（JSONB）"),
        ("permissions", 24, 32768, "32 kB", 3, "权限表"),
    ]
    _COLUMNS = {
        "users": [("user_id", "int8", "NO", None), ("nickname", "varchar", "NO", None), ("last_updated", "timestamp", "YES", None)],
        "user_group": [("group_id", "int8", "NO", None), ("group_name", "varchar", "YES", None)],
        "user_info": [("user_id", "int8", "NO", None), ("info", "jsonb", "YES", None), ("last_updated", "timestamp", "YES", None)],
        "permissions": [("user_id", "int8", "NO", None), ("permission_type", "permission_type", "NO", None), ("granted_by", "int8", "YES", None)],
        "message": [("sole_id", "bigserial", "NO", "nextval('message_sole_id_seq'::regclass)"), ("message_id", "int8", "NO", None), ("user_id", "int8", "NO", None), ("group_id", "int8", "YES", None), ("time", "int8", "NO", None), ("message_content", "text", "YES", None)],
        "atri_memory": [("memory_id", "bigserial", "NO", "nextval('atri_memory_memory_id_seq'::regclass)"), ("user_id", "int8", "YES", None), ("group_id", "int8", "YES", None), ("event_time", "timestamp", "NO", None), ("event", "text", "NO", None), ("event_vector", "vector", "YES", None), ("category", "memory_category", "NO", None), ("importance", "int4", "NO", None), ("credibility", "int4", "NO", None), ("access_count", "int4", "YES", "0"), ("last_accessed", "timestamp", "YES", None)],
        "chat_context": [("context_id", "bigserial", "NO", "nextval('chat_context_context_id_seq'::regclass)"), ("user_id", "int8", "YES", None), ("group_id", "int8", "YES", None), ("context_data", "jsonb", "YES", None), ("total_tokens", "int4", "YES", None), ("play_role", "varchar", "YES", None), ("last_updated", "timestamp", "YES", None)],
        "token_statistics": [("id", "bigserial", "NO", "nextval('token_statistics_id_seq'::regclass)"), ("user_id", "int8", "YES", None), ("group_id", "int8", "YES", None), ("model", "varchar", "YES", None), ("prompt_tokens", "int4", "YES", None), ("completion_tokens", "int4", "YES", None), ("total_tokens", "int4", "YES", None), ("created_at", "timestamp", "YES", "CURRENT_TIMESTAMP")],
    }
    _CONSTRAINTS = {
        "users": [("users_pkey", "p", "PRIMARY KEY (user_id)")],
        "user_group": [("user_group_pkey", "p", "PRIMARY KEY (group_id)")],
        "permissions": [("permissions_pkey", "p", "PRIMARY KEY (user_id)")],
        "message": [("message_pkey", "p", "PRIMARY KEY (sole_id)")],
        "atri_memory": [("atri_memory_pkey", "p", "PRIMARY KEY (memory_id)"), ("atri_memory_importance_check", "c", "CHECK ((importance >= 1) AND (importance <= 10))")],
        "chat_context": [("chat_context_pkey", "p", "PRIMARY KEY (context_id)"), ("chat_context_user_group_check", "c", "CHECK ((user_id IS NULL) <> (group_id IS NULL))")],
        "token_statistics": [("token_statistics_pkey", "p", "PRIMARY KEY (id)")],
        "user_info": [("user_info_pkey", "p", "PRIMARY KEY (user_id)")],
    }
    _INDEXES = {
        "message": [("message_pkey", "CREATE UNIQUE INDEX message_pkey ON public.message USING btree (sole_id)"), ("idx_message_user_time", "CREATE INDEX idx_message_user_time ON public.message USING btree (user_id, time DESC)")],
        "atri_memory": [("atri_memory_pkey", "CREATE UNIQUE INDEX atri_memory_pkey ON public.atri_memory USING btree (memory_id)"), ("idx_memory_vector", "CREATE INDEX idx_memory_vector ON public.atri_memory USING hnsw (event_vector vector_cosine_ops)")],
        "users": [("users_pkey", "CREATE UNIQUE INDEX users_pkey ON public.users USING btree (user_id)")],
        "chat_context": [("chat_context_pkey", "CREATE UNIQUE INDEX chat_context_pkey ON public.chat_context USING btree (context_id)")],
    }

    async def execute_SQL(self, sql, args=None):
        # 引号在关键词匹配前去掉，兼容 FROM "table" 写法
        s = " ".join(sql.lower().split()).replace('"', "")
        # 数据库页的 pg_catalog / information_schema 查询
        if "pg_postmaster_start_time" in s:
            return [{"version": "PostgreSQL 16.4 (Ubuntu 16.4-1.pgdg22.04+2) on x86_64", "db_name": "atri", "db_size": "156 MB", "uptime": "3 days, 04:12:33", "connections": 4}]
        if "from pg_class" in s:
            return [
                {"table_name": t, "row_estimate": est, "size_bytes": size, "size_pretty": pretty, "column_count": cols, "comment": cmt}
                for t, est, size, pretty, cols, cmt in self._TABLE_SIZES
            ]
        if "information_schema.columns" in s:
            name = next((x for x in (args or []) if isinstance(x, str) and not x.startswith("%")), "")
            cols = self._COLUMNS.get(name.lower(), [])
            return [
                {"column_name": c, "udt_name": u, "is_nullable": nul, "column_default": dflt, "character_maximum_length": 64 if u == "varchar" else None}
                for c, u, nul, dflt in cols
            ]
        if "from pg_indexes" in s:
            name = next((x for x in (args or []) if isinstance(x, str)), "")
            return [{"indexname": i, "indexdef": d} for i, d in self._INDEXES.get(name.lower(), [])]
        if "pg_constraint" in s:
            name = next((x for x in (args or []) if isinstance(x, str)), "")
            return [{"name": n, "type": t, "def": d} for n, t, d in self._CONSTRAINTS.get(name.lower(), [])]
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
            rows = self._rows_for(s, like, eq_vals)
            if rows or like or eq_vals or "where" in s:
                return [{"c": len(rows)}]
            # 其余表（chat_context 等）无行集数据时，用行数估计兜底
            est = next((r for r in self._TABLE_SIZES if f"from {r[0]}" in s), None)
            return [{"c": est[1] if est else 0}]
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
        m = re.search(r"limit (\d+)(?: offset (\d+))?", s)
        if m:
            limit, offset = int(m.group(1)), int(m.group(2) or 0)
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


class _MockConnection:
    """假连接对象：只提供面板读取的 is_connected 状态"""

    is_connected = True


class _MockOneBotAdapter:
    """罐头 OneBot 适配器：常用 action 返回真实形状的假数据，其余回显请求"""

    source_name = "onebot"
    is_started = True

    _CANNED = {
        "get_login_info": lambda: {"user_id": 10000, "nickname": "ATRI-dev"},
        "get_group_list": lambda: [
            {"group_id": g["group_id"], "group_name": g["group_name"], "member_count": 10, "max_member_count": 200}
            for g in MockDatabase._GROUPS
        ],
        "get_friend_list": lambda: [
            {"user_id": u["user_id"], "nickname": u["nickname"]} for u in MockDatabase._USERS
        ],
    }

    def __init__(self):
        self._connection = _MockConnection()

    async def call_api(self, action: str, params: dict):
        await asyncio.sleep(0.2)  # 模拟网络往返
        data = self._CANNED.get(action, lambda: {"echo": {"action": action, "params": params}})()
        return {"status": "ok", "retcode": 0, "data": data, "echo": "mock"}


class _MockPlatformManager(PlatformManager):
    """预置一个假 napcat 适配器，使调用接口页与平台状态在开发模式下可用（跳过父类构造的容器依赖）"""

    def __init__(self):
        self._adapters = {"napcat": _MockOneBotAdapter()}


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


class _MockToolset:
    def __init__(self, names):
        self._names = list(names)

    def names(self):
        return list(self._names)


class _MockPresetManager:
    """预置假工具预设，供 LLM 工具页展示归属关系"""

    def __init__(self):
        self.presets = {
            "group_chat": _MockToolset(["web_search", "tool_search"]),
            "agency_Agent": _MockToolset([]),
        }
        self.deferred = {"group_chat": ["run_python_code"]}


class _MockRegistry:
    def __init__(self, func_list):
        self.func_list = func_list

    def get_func(self, name):
        return next((t for t in self.func_list if t.name == name), None)


class _MockToolCalls:
    """预置本地 + MCP 假工具，使 LLM 工具页在开发模式下可渲染与测试"""

    def __init__(self):

        async def _web_search(query: str, search_depth: str = "basic"):
            return json.dumps(
                [
                    {"title": f"「{query}」的结果 1（mock）", "url": "https://example.com/1", "content": "开发模式下的假搜索结果，验证 JSON 字符串序列化。"},
                    {"title": f"「{query}」的结果 2（mock）", "url": "https://example.com/2", "content": "第二条假结果。"},
                ],
                ensure_ascii=False,
            )

        async def _get_user_info(user_id: int):
            return {"user_id": user_id, "nickname": "测试用户甲（mock）", "impression": "一位喜欢深夜听爵士乐的用户。"}

        async def _tool_search(query: str, limit: int = 1):
            raise ToolSearchRequested(query=query, limit=limit)

        async def _send_image_message(url: str, message_data=None):
            return "不应在面板执行到这里"

        class _FakeMcpTool:
            def __init__(self, name):
                self.name = name

        class _FakeSession:
            async def call_tool(self, name, arguments=None):
                if name == "get_forecast":
                    raise Exception("天气服务不可用（mock 错误演示）")
                return {"city": (arguments or {}).get("city"), "weather": "晴", "temperature": 26}

        class _FakeClient:
            def __init__(self):
                self.session = _FakeSession()

        client = _FakeClient()

        def _local(name, desc, props, handler, **kw):
            return LocalTool(
                name=name, description=desc,
                parameters={"type": "object", "properties": props},
                handler=handler, **kw,
            )

        def _mcp(name, desc, props, **kw):
            return MCPTool(
                name=name, description=desc,
                parameters={"type": "object", "properties": props},
                mcp_tool=_FakeMcpTool(name), mcp_client=client, mcp_server_name="weather",
                **kw,
            )

        self._registry = _MockRegistry(
            [
                _local(
                    "web_search", "联网搜索（mock）",
                    {
                        "query": {"type": "string", "description": "搜索关键词"},
                        "search_depth": {"type": "string", "enum": ["basic", "advanced"], "default": "basic"},
                    },
                    _web_search, concurrent=True,
                ),
                _local(
                    "get_user_info", "获取用户 user_info 文档（mock）",
                    {"user_id": {"type": "integer", "description": "用户 QQ 号"}},
                    _get_user_info,
                ),
                _local(
                    "tool_search", "搜索待发现工具（mock，演示异常输出）",
                    {"query": {"type": "string", "description": "关键词"}, "limit": {"type": "integer", "default": 1, "minimum": 1}},
                    _tool_search,
                ),
                _local(
                    "send_image_message", "发送图片消息（依赖消息上下文，演示不可测试状态）",
                    {"url": {"type": "string", "description": "图片 URL"}},
                    _send_image_message, chat_scope="private",
                ),
                _mcp("query_weather", "查询城市天气（mock MCP）", {"city": {"type": "string", "description": "城市名"}}),
                _mcp("get_forecast", "查询城市预报（mock MCP，演示执行失败）", {"city": {"type": "string"}, "days": {"type": "integer", "default": 3}}, chat_scope="group"),
            ]
        )
        self._preset_manager = _MockPresetManager()

    async def calls(self, tool_name: str, arguments_str: str, message_data=None):
        tool = self._registry.get_func(tool_name)
        if tool is None:
            raise Exception(f"Request function {tool_name} not found.")
        return await tool.execute(message_data=None, **json.loads(arguments_str))


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
