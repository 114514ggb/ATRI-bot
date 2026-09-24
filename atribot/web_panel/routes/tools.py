"""命令与 LLM 工具：命令注册表元数据、工具清单、面板内工具测试"""

import asyncio
import inspect
import json
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from atribot.core.service_container import container

from ..deps import _auth

router = APIRouter()


@router.get("/api/commands")
async def api_commands(_: None = Depends(_auth)) -> List[Dict[str, Any]]:
    from atribot.core.command.command_parsing import CommandSystem

    cmd: CommandSystem = container.get_by_type(CommandSystem)
    result: List[Dict[str, Any]] = []
    for name, c in cmd.command_registry.items():
        params = [
            {
                "name": p.name,
                "type": p.param_type.value,
                "data_type": getattr(p.type, "__name__", str(p.type)),
                "description": p.description,
                "required": p.required,
                "default": str(p.default) if p.default is not None else None,
                "short_option": p.short_option,
                "long_option": p.long_option,
                "choices": p.choices,
                "metavar": p.metavar,
                "multiple": p.multiple,
            }
            for p in c.params.values()
        ]
        result.append(
            {
                "name": name,
                "description": c.description,
                "aliases": c.aliases,
                "authority_level": c.authority_level,
                "cooldown": c.cooldown,
                "usage": c.get_usage_string(),
                "examples": c.examples,
                "params": params,
            }
        )
    return sorted(result, key=lambda x: x["name"])


def _tool_calls_service():
    """惰性获取 ToolCalls 服务；未注册（bot 未启动/独立面板）时返回 None"""
    if not container.exists("ToolCalls"):
        return None
    return container.get("ToolCalls")


def _local_tool_needs_message_data(tool) -> bool:
    """判断本地工具 handler 是否声明了 message_data 参数（声明即依赖聊天上下文）"""
    try:
        return "message_data" in inspect.signature(tool.handler).parameters
    except (TypeError, ValueError):
        return True


def _serialize_tool(tc, tool) -> Dict[str, Any]:
    from atribot.LLMchat.MCP.tool_model import MCPTool

    entry: Dict[str, Any] = {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters or {"type": "object", "properties": {}},
        "active": tool.active,
        "concurrent": tool.concurrent,
        "background": tool.background,
        "chat_scope": tool.chat_scope,
        "source": "mcp" if isinstance(tool, MCPTool) else "local",
        "mcp_server": getattr(tool, "mcp_server_name", None) if isinstance(tool, MCPTool) else None,
        "source_detail": None,
        "testable": True,
        "testable_reason": None,
        "presets": {},
    }
    if isinstance(tool, MCPTool):
        entry["source_detail"] = f"MCP 服务: {tool.mcp_server_name}"
    else:
        entry["source_detail"] = getattr(tool.handler, "__module__", "") or None
        if _local_tool_needs_message_data(tool):
            entry["testable"] = False
            entry["testable_reason"] = "依赖聊天消息上下文(message_data)"

    pm = getattr(tc, "_preset_manager", None)
    if pm is not None:
        for preset_name, toolset in getattr(pm, "presets", {}).items():
            try:
                if tool.name in toolset.names():
                    entry["presets"][preset_name] = "default"
            except Exception:
                continue
        for preset_name, deferred_names in (getattr(pm, "deferred", None) or {}).items():
            if tool.name in deferred_names:
                entry["presets"][preset_name] = "deferred"
    return entry


@router.get("/api/tools")
async def api_tools(_: None = Depends(_auth)) -> Dict[str, Any]:
    tc = _tool_calls_service()
    if tc is None:
        return {"available": False, "tools": [], "mcp_servers": []}

    tools: List[Dict[str, Any]] = []
    server_count: Dict[str, int] = {}
    for tool in tc._registry.func_list:
        entry = _serialize_tool(tc, tool)
        if entry["mcp_server"]:
            server_count[entry["mcp_server"]] = server_count.get(entry["mcp_server"], 0) + 1
        tools.append(entry)
    tools.sort(key=lambda x: (x["source"], x["mcp_server"] or "", x["name"]))
    sandbox_tools = _sandbox_tools_info(tc)
    mcp_servers = [{"name": n, "tool_count": c} for n, c in sorted(server_count.items())]
    return {
        "available": True,
        "tools": tools,
        "mcp_servers": mcp_servers,
        "sandbox_tools": sandbox_tools,
    }


def _sandbox_tools_info(tc) -> Dict[str, Any]:
    """汇总沙盒依赖工具的环境与启用状态（供面板展示/一键刷新）"""
    try:
        from atribot.LLMchat.tools.sandbox_tools import (
            SANDBOX_TOOL_NAMES,
            env_facts,
            sandbox_active,
        )

        facts = env_facts()
        return {
            "names": list(SANDBOX_TOOL_NAMES),
            "facts": facts,
            "active": {name: sandbox_active(name) for name in SANDBOX_TOOL_NAMES},
            "work_dir": facts.get("work_dir"),
        }
    except Exception as e:
        return {"names": [], "facts": {}, "active": {}, "error": str(e)}


@router.post("/api/tools/refresh")
async def api_tools_refresh(_: None = Depends(_auth)) -> Dict[str, Any]:
    """全量重载本地工具（沙盒环境/描述刷新），并重建 schema 缓存"""
    tc = _tool_calls_service()
    if tc is None:
        raise HTTPException(status_code=503, detail="ToolCalls 服务未就绪")
    try:
        changed = tc.reload_local_tools()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重载本地工具失败：{e}")
    return {"status": "reloaded", "changed_tools": changed or []}


def _tool_result_to_json(result: Any) -> Any:
    """把工具返回值转为可 JSON 序列化的结构"""
    if result is None:
        return None
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (ValueError, TypeError):
            return result
    if hasattr(result, "model_dump"):
        try:
            return result.model_dump(mode="json")
        except Exception:
            pass
    try:
        json.dumps(result)
        return result
    except (TypeError, ValueError):
        return str(result)


class ToolTestBody(BaseModel):
    name: str
    arguments: Dict[str, Any] = {}


@router.post("/api/tools/test")
async def api_tools_test(body: ToolTestBody, _: None = Depends(_auth)) -> Dict[str, Any]:
    from atribot.LLMchat.MCP.tool_model import LocalTool

    tc = _tool_calls_service()
    if tc is None:
        raise HTTPException(status_code=503, detail="工具系统不可用（bot 未启动或 ToolCalls 未注册）")
    tool = tc._registry.get_func(body.name)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"工具 {body.name} 不存在")
    if isinstance(tool, LocalTool) and _local_tool_needs_message_data(tool):
        raise HTTPException(
            status_code=400,
            detail=f"工具 {body.name} 依赖聊天消息上下文(message_data)，无法在面板测试",
        )

    start = time.time()
    try:
        raw = await asyncio.wait_for(
            tc.calls(body.name, json.dumps(body.arguments, ensure_ascii=False), None),
            timeout=60,
        )
    except asyncio.TimeoutError:
        return {"ok": False, "error": "执行超时（60 秒）", "duration_ms": 60000}
    except Exception as e:
        # 工具自身抛错（含 tool_search 的 ToolSearchRequested）属于正常测试输出
        return {
            "ok": False,
            "error": str(e) or repr(e),
            "duration_ms": int((time.time() - start) * 1000),
        }
    return {
        "ok": True,
        "result": _tool_result_to_json(raw),
        "duration_ms": int((time.time() - start) * 1000),
    }
