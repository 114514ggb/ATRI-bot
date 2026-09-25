"""面板独立开发/调试服务器

用法:
    python -m atribot.web_panel.dev_server
    # 打开 http://127.0.0.1:5125/admin/ ，访问令牌: dev-token

mock 实现（假数据库 / 命令 / 工具 / 日志流）在 dev_mocks.py。
"""

import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

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
        "web_panel": {"enable": True, "access_token": DEV_TOKEN, "port": 5125},
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
            "group_chat": {"default": ["web_search", "memory_search", "tool_search"], "deferred": ["run_python_code"]},
            "private_chat": {"default": ["web_search", "tool_search"], "deferred": ["run_python_code", "send_file"]},
            "agency_Agent": ["run_command"],
            "webui": {"default": ["web_search", "tool_search"], "deferred": ["run_python_code"]},
        },
        "group_white_list": [123456, 789012],
        "group_initiative_chat_white_list": [123456],
        "group_information_extraction": [],
        "private_chat_white_list": [10086],
        "database": {"host": "127.0.0.1", "port": 5432, "user": "postgres", "password": "dev", "database": "atri"},
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

    # 头像：把项目 assets 下的 ATRI-bot 图带进开发环境，聊天页可预览真实头像
    for cand in ("ATRI-bot.png", "ATRI-bot.jpg", "ATRI-bot.jpeg", "ATRI-bot.webp", "ATRI-bot.gif"):
        src = PROJECT_ROOT / "assets" / cand
        if src.is_file():
            shutil.copy(src, tmp / cand)
            break
    return tmp


def main() -> None:
    # dev 模式不写 bot 的日志文件：logger.py 默认会打开 atribot/log/atri_log_，
    # 与主进程共用同一文件会导致跨天轮转互相锁死（WinError 32），只留控制台输出
    os.environ.setdefault("ATRI_FILE_LOG", "0")

    tmp = _prepare_files()
    os.environ["ATRI_CONFIG_PATH"] = str(tmp / "config.json")

    import uvicorn
    from fastapi import FastAPI

    from atribot.core.atri_config import atriConfig
    from atribot.core.command.async_permissions_management import PermissionsManagement
    from atribot.core.service_container import container
    from atribot.LLMchat.sandbox.factory import create_sandbox
    from atribot.web_panel.dev_mocks import (
        MockDatabase,
        _fake_log_stream,
        _FakeCommandSystem,
        _MockPlatformManager,
        _MockToolCalls,
        make_llm_supplier_mock,
        make_media_processor_mock,
        make_memory_mock,
    )
    from atribot.web_panel.panel_router import _ensure_log_handler, mount_static, router

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s | %(message)s")

    container.register("config", atriConfig())
    container.register("database", MockDatabase())

    # 沙盒（容器管理页）：开发模式直接用本机直执行后端，无需 Docker
    sand_box = create_sandbox({"type": "none", "work_dir": str(tmp / "sandbox_workspace")})
    container.register("SandBox", sand_box, cleanup=sand_box.stop)
    container.register("PlatformManager", _MockPlatformManager())
    container.register("PermissionsManagement", PermissionsManagement())
    container.register("CommandSystem", _FakeCommandSystem())
    container.register("ToolCalls", _MockToolCalls())
    # 聊天页（SubAgentRunner）在开发模式下的最小服务集
    # （Logger 无需注册：导入链已在容器中登记了 "log" 服务，get_by_type(Logger) 可直接命中）
    container.register("MemorySystem", make_memory_mock())
    container.register("MediaProcessor", make_media_processor_mock())
    container.register("LLMConnectionManager", make_llm_supplier_mock())

    app = FastAPI(title="ATRI Admin Panel (dev)")
    app.include_router(router)
    mount_static(app)  # 静态资源 no-store 由 mount_static 统一注册

    @app.middleware("http")
    async def _slow_api_sim(request, call_next):
        """可选的接口延迟模拟（ATRI_DEV_DELAY_MS=1500），用于调试面板加载态"""
        delay = int(os.environ.get("ATRI_DEV_DELAY_MS", "0"))
        if delay and request.url.path.startswith("/admin/api"):
            await asyncio.sleep(delay / 1000)
        return await call_next(request)

    @app.on_event("startup")
    async def _start_fake_logs() -> None:
        _ensure_log_handler()
        asyncio.get_event_loop().create_task(_fake_log_stream())
        await sand_box.start()

    port = int(os.environ.get("ATRI_PANEL_PORT", "5125"))
    print(f"[dev_server] 临时配置目录: {tmp}")
    print(f"[dev_server] 面板地址: http://127.0.0.1:{port}/admin/  访问令牌: {DEV_TOKEN}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
