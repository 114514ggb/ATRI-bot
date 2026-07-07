from logging import Logger
from typing import List

from atribot.core.atri_config import atriConfig
from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage
from atribot.LLMchat.agent.agent_data import AgentData
from atribot.LLMchat.agent.context.context import AgentContext
from atribot.LLMchat.agent.runners.response import RunSummary
from atribot.LLMchat.agent.runners.subagent.sub_agent_runner import SubAgentRunner
from atribot.LLMchat.MCP.tool_calls import ToolCalls

SUB_AGENT_SYSTEM_PROMPT: str = (
    "你是助手的子代理，负责执行主助手委派给你的具体任务。\n"
    "\n"
    "## 行为准则\n"
    "1. 专注于被分配的任务，不要偏离主题或做无关操作。\n"
    "2. 充分利用你可以调用的工具来收集信息、执行操作、验证结果。\n"
    "3. 遇到不确定的情况时，基于已有信息做出最佳判断，不要反复确认。\n"
    "4. 任务完成后，给出简洁明了的结论或摘要，包含关键发现和结果。\n"
    "\n"
    "## 输出要求\n"
    "- 完成后输出任务的核心结论，格式清晰易读。\n"
    "- 如果任务无法完成，说明原因并给出已获取的部分信息。\n"
    "- 不要在无关细节上过度展开，保持回复精炼。\n"
)

_MAX_TURNS = 20
"""子代理最大执行轮数"""


@ToolCalls.register_tool(
    name="sub_agent",
    description=(
        "委托一个复杂、多步骤的任务给子代理独立执行。"
        "子代理拥有独立的工具集和LLM交互循环,可以进行多步推理、"
        "组合使用工具、并在完成后返回结构化的结果"
        "适用于查找资料或是深度寻找相关记忆,需要独立上下文执行的只用关注结果的复杂任务"
    ),
    properties={
        "task": {
            "type": "string",
            "description": (
                "要委托给子代理的详细任务描述。应包含：任务目标、"
                "具体要求和约束条件、期望的输出格式,越详细越好"
            ),
        },
    },
)
async def sub_agent_task(
    task: str,
    message_data: ChatMessage,
) -> str:
    """子代理工具入口 —— 创建独立 Agent 执行委派任务并返回结果。

    Args:
        task: 委派任务描述
        message_data: 触发此工具调用的聊天消息上下文

    Returns:
        子代理执行结果字符串
    """
    if not task or not task.strip():
        return "子代理执行失败: 任务描述不能为空"
    
    log: Logger = container.get_by_type(Logger).getChild("SubAgentTool")
    config: atriConfig = container.get("config")

    agency_cfg = getattr(config.model, "agency_Agent", None)
    if agency_cfg and agency_cfg.get("model_name"):
        model_name = agency_cfg["model_name"]
        supplier_name = agency_cfg.get("supplier", "")
    else:
        summarize_cfg = config.model.memory.summarize_model
        model_name = summarize_cfg["model_name"]
        supplier_name = summarize_cfg.get("supplier", "")
        log.info(f"未配置 model.agency_Agent,回退到 summarize_model 模型: {model_name}")

    if not model_name:
        return "子代理执行失败: 配置中未找到有效的模型名称"

    if agency_preset := config.tool_presets.agency_Agent:
        tool_names = agency_preset
    else:
        log.warning("config.json 中未配置 agency_Agent 工具预设，子代理将无工具可用")
        tool_names: List[str] = []

    log.info(
        f"子代理启动: model={model_name}, supplier={supplier_name}, "
        f"tools={tool_names}, max_turns={_MAX_TURNS}"
    )

    context = AgentContext()
    context.play_role = SUB_AGENT_SYSTEM_PROMPT + f"环境的群号是:{message_data.group_id}"
    context.add_user_message(content=task)

    agent_data = AgentData(
        context=context,
        model_name=model_name,
        supplier=supplier_name,
        tools=tool_names,
        kwargs={
            "temperature": 0.3,
            "top_p": 0.90,
            "max_tokens": 32768,
            "tool_choice": "auto",
        },
    )

    runner = SubAgentRunner(agent_data=agent_data, message_data=message_data)

    final_summary: RunSummary | None = None
    error_message: str | None = None

    try:
        async for event in runner.run(max_turns=_MAX_TURNS):
            if event.event_type.name == "RUN_SUMMARY":
                final_summary = event
            elif event.event_type.name == "ERROR":
                error_message = getattr(event, "error_message", str(event))
                log.error(f"子代理运行出错: {error_message}")
    except Exception as exc:
        log.exception(f"子代理执行异常: {exc}")
        return f"子代理执行失败: {type(exc).__name__}: {exc}"

    if final_summary is not None and final_summary.total_content:
        result = final_summary.total_content.strip()
        finish_reason = final_summary.finish_reason

        if finish_reason == "max_turns":
            result += f"\n\n[子代理达到最大轮次 {_MAX_TURNS}，以上为当前进度下的部分结果]"
        elif finish_reason == "error":
            result += "\n\n[子代理执行过程中遇到错误]"

        return result

    if error_message:
        return f"子代理执行失败: {error_message}"

    return "子代理执行完成，但未产出有效结果。"