import json
from logging import Logger
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from mcp.types import BlobResourceContents, CallToolResult, TextResourceContents

from atribot.core.service_container import container
from atribot.core.type.chat_message_types import ChatMessage
from atribot.core.type.context_types import ToolCallsStopIteration
from atribot.LLMchat.agent.agent_data import AgentData
from atribot.LLMchat.agent.context.context import AgentContext
from atribot.LLMchat.agent.message import (
    AssistantMessage,
    AudioSegment,
    ImageBase64Segment,
    MessageSegment,
    TextSegment,
    ToolMessage,
)
from atribot.LLMchat.agent.runners.base_runner import AgentState, BaseAgentRunner
from atribot.LLMchat.agent.runners.response import (
    AgentEvent,
    StepSummary,
    agent_error,
    reasoning_delta,
    run_summary,
    step_summary,
    text_delta,
    tool_call_result,
    tool_call_start,
)
from atribot.LLMchat.MCP.tool_calls import ToolCalls
from atribot.LLMchat.media_processor import MediaProcessor
from atribot.LLMchat.model_api.ai_connection_manager import LLMConnectionManager
from atribot.LLMchat.model_api.llm_types import ChatCompletion, ChatCompletionChunk, ToolCall, message
from atribot.LLMchat.model_api.model_api_basics import model_api_basics

_MAX_TOOL_ROUNDS = 10  # 单步内工具调用最大轮数
_MAX_EMPTY_RETRIES = 5  # 空响应重试次数
_TOOL_OUTPUT_TRUNCATE = 20000  # 工具返回结果截断长度


class SubAgentRunner(BaseAgentRunner): 
    """子 Agent 执行器 —— 管理完整 LLM 交互生命周期"""

    def __init__(
        self, agent_data: AgentData, message_data: ChatMessage | None = None
    ) -> None:
        super().__init__(agent_data)
        self.log: Logger = container.get_by_type(Logger).getChild("SubAgent")
        self._tool_calls_mgr: ToolCalls = container.get("ToolCalls")
        self._media_processor: MediaProcessor = container.get("MediaProcessor")
        self._message_data: ChatMessage | None = message_data

        # 多模态能力
        self._visual_sense: bool = False
        self._audio_sense: bool = False
        self._resolve_model_capabilities()

        # 按名称解析到的供应商 API 对象缓存
        self.__cached_supplier_api: Optional[model_api_basics] = None

        #步状态
        self._step_index: int = 0
        self._hooks_triggered: bool = False

        #增量上下文
        self._increase_context: AgentContext = AgentContext()

        #最后一次 LLM 响应结果
        self._last_api_reply: Optional[ChatCompletion] = None
        self._last_assistant_message: Optional[message] = None
        self._last_content: Optional[str] = None

        #当前步的 StepSummary
        self._last_summary: Optional[StepSummary] = None

    @property
    def _supplier_api(self) -> model_api_basics:
        """按 ``self.agent_data.supplier`` 名称查找并缓存供应商 API 对象"""
        if self.__cached_supplier_api is None:
            supplier_mgr = container.get_by_type(LLMConnectionManager)
            conn = supplier_mgr.connections.get(self.agent_data.supplier)
            if conn is None:
                raise ValueError(
                    f"供应商 '{self.agent_data.supplier}' 未在 "
                    f"LLMConnectionManager 中注册"
                )
            self.__cached_supplier_api = conn.connection_object
        return self.__cached_supplier_api

    def _resolve_model_capabilities(self) -> None:
        """设置多模态值"""
        supplier_mgr = container.get_by_type(LLMConnectionManager)
        model_name: str = self.agent_data.model_name
        supplier_name: str = self.agent_data.supplier

        conn = supplier_mgr.connections.get(supplier_name)
        if conn is not None:
            model_info = conn.model_dict.get(model_name, {})
            self._visual_sense = model_info.get("visual_sense", False)
            self._audio_sense = model_info.get("audio_sense", False)
        else:
            self.log.warning(
                f"未找到供应商 '{supplier_name}' 的模型 {model_name} 的多模态能力配置，"
                f"默认 visual_sense=False, audio_sense=False"
            )

    def _get_tool_json(self) -> Optional[List[Dict[str, Any]]]:
        """获取 OpenAI 格式工具定义"""
        if not self.agent_data.tools:
            return []
        return self._tool_calls_mgr.get_func_desc_openai_style(
            names=self.agent_data.tools
        )

    def _build_payload_messages(self) -> List[Dict[str, Any]]:
        """拼接完整消息列表"""
        return self.agent_data.context.to_openai_list() + self._increase_context.to_openai_list()

    async def _trigger_before_run(self) -> None:
        """触发 ``before_run`` 钩子(仅一次)"""
        if self._hooks_triggered:
            return
        self._hooks_triggered = True
        for hook in self.agent_data.hooks:
            try:
                await hook.before_run(self.agent_data)
            except Exception as e:
                self.log.error(
                    f"before_run hook failed ({type(hook).__name__}): {e}"
                )

    async def _trigger_on_tool_call(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> None:
        """触发 ``on_tool_call`` 钩子"""
        for hook in self.agent_data.hooks:
            try:
                await hook.on_tool_call(self.agent_data, tool_name, arguments)
            except Exception as e:
                self.log.error(
                    f"on_tool_call hook failed ({type(hook).__name__}): {e}"
                )

    async def _trigger_on_tool_return(
        self, tool_name: str, result: Any
    ) -> None:
        """触发 ``on_tool_return`` 钩子"""
        for hook in self.agent_data.hooks:
            try:
                await hook.on_tool_return(self.agent_data, tool_name, result)
            except Exception as e:
                self.log.error(
                    f"on_tool_return hook failed ({type(hook).__name__}): {e}"
                )

    async def _trigger_on_error(self, error: Exception) -> None:
        """触发 ``on_error`` 钩子"""
        for hook in self.agent_data.hooks:
            try:
                await hook.on_error(self.agent_data, error)
            except Exception as e:
                self.log.error(
                    f"on_error hook failed ({type(hook).__name__}): {e}"
                )

    async def _trigger_after_run(self, response: Any) -> None:
        """触发 ``after_run`` 钩子"""
        for hook in self.agent_data.hooks:
            try:
                await hook.after_run(self.agent_data, response)
            except Exception as e:
                self.log.error(
                    f"after_run hook failed ({type(hook).__name__}): {e}"
                )

    async def _request_llm_nonstream(
        self,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[str]]:
        """非流式 LLM 请求

        Returns:
            (api_reply, assistant_message, content)

        Raises:
            ValueError: 在最大重试次数后仍未获取有效回复
        """
        model_api = self._supplier_api
        model = self.agent_data.model_name
        messages = self._build_payload_messages()
        tools = self._get_tool_json()
        custom_params = self.agent_data.kwargs

        for _ in range(_MAX_EMPTY_RETRIES):
            if custom_params:
                payload: Dict[str, Any] = {
                    **custom_params,
                    "messages": messages,
                }
                if tools is not None:
                    payload["tools"] = tools
                api_reply = await model_api.generate_json_ample(
                    model=model, remainder=payload
                )
            else:
                api_reply = await model_api.generate_text_tools(
                    model=model, messages=messages, tools=tools or []
                )

            self.log.debug(f"LLM response: {api_reply}")

            if not api_reply.get("choices"):
                continue

            assistant_message = api_reply["choices"][0]["message"]
            content = assistant_message.get("content")

            if content:
                return api_reply, assistant_message, content
            if assistant_message.get("tool_calls"):
                return api_reply, assistant_message, None

        raise ValueError(
            f"在 {_MAX_EMPTY_RETRIES} 次尝试后仍未能获取有效回复"
        )

    async def _request_llm_stream(
        self,
    ) -> AsyncGenerator[AgentEvent, None]:
        """流式 LLM 请求,逐 chunk 消费，实时 yield ``AgentEvent``

        Yields:
            - ``ReasoningDeltaChunk`` — 思考过程增量
            - ``TextDeltaChunk`` — 文本增量
            - ``ToolCallStartChunk`` — 工具调用开始(首次检测到完整工具名时)
            - ``AgentStatusChunk`` — 状态变更
        """
        model_api = self._supplier_api
        model = self.agent_data.model_name
        messages = self._build_payload_messages()
        tools = self._get_tool_json()
        custom_params = self.agent_data.kwargs

        payload: Dict[str, Any] = {
            **custom_params,
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if tools is not None:
            payload["tools"] = tools

        #流式状态
        reasoning_content = ""
        content = ""
        tool_calls: List[Dict[str, Any]] = []
        usage: Optional[Dict[str, Any]] = None
        # 用于跟踪已产出 ToolCallStartChunk 的工具(按 index 记录工具名)
        _started_tool_names: Dict[int, str] = {}

        async for chunk in model_api.client_post_stream(payload):
            chunk:ChatCompletionChunk
            
            choices = chunk.get("choices")
            if not choices:
                continue

            delta = choices[0].get("delta", {})

            if dr := delta.get("reasoning_content"):
                reasoning_content += dr
                yield reasoning_delta(delta=dr, step_index=self._step_index)

            if dc := delta.get("content"):
                content += dc
                yield text_delta(delta=dc, step_index=self._step_index)

            if dtc := delta.get("tool_calls"):
                for tool_call_delta in dtc:
                    index: int = tool_call_delta.get("index", len(tool_calls))

                    while len(tool_calls) <= index:
                        tool_calls.append({
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                            "index": len(tool_calls),
                        })

                    current = tool_calls[index]

                    if "id" in tool_call_delta:
                        current["id"] += tool_call_delta["id"]

                    if "type" in tool_call_delta:
                        current["type"] = tool_call_delta["type"]

                    if "function" in tool_call_delta:
                        df = tool_call_delta["function"]
                        cf = current["function"]

                        if "name" in df:
                            cf["name"] += df["name"]

                        if "arguments" in df:
                            cf["arguments"] += df["arguments"]

                    tool_name = current["function"]["name"]
                    if tool_name and index not in _started_tool_names:
                        _started_tool_names[index] = tool_name
                        yield tool_call_start(
                            tool_name=tool_name,
                            tool_call_id=current["id"] or tool_name,
                            arguments={},
                            step_index=self._step_index,
                        )

            # 捕获 usage(通常出现在最后一个 chunk)
            if "usage" in chunk:
                usage = chunk["usage"]

        #组装最终消息
        assistant_message: Dict[str, Any] = {"role": "assistant"}
        if reasoning_content:
            assistant_message["reasoning_content"] = reasoning_content
        if content:
            assistant_message["content"] = content
        if tool_calls:
            # 清理内部标记字段
            for tc in tool_calls:
                tc.pop("index", None)
            assistant_message["tool_calls"] = tool_calls

        api_reply: Dict[str, Any] = {
            "choices": [{"index": 0, "message": assistant_message}],
        }
        if usage:
            api_reply["usage"] = usage

        # 写入实例状态
        self._last_api_reply = api_reply
        self._last_assistant_message = assistant_message
        self._last_content = content or None

    async def _do_llm_request(self) -> AsyncGenerator[AgentEvent, None]:
        """统一的 LLM 请求入口，流式/非流式自动分发"""
        if self.stream:
            async for event in self._request_llm_stream():
                yield event
        else:
            (
                self._last_api_reply,
                self._last_assistant_message,
                self._last_content,
            ) = await self._request_llm_nonstream()

    async def _format_mcp_result(
        self,
        result: CallToolResult,
        name: str,
        tool_call_id: str,
    ) -> ToolMessage:
        """将 MCP 工具执行结果格式化为 ``ToolMessage``

        Args:
            result: MCP 工具返回值
            name: 工具名称
            tool_call_id: 工具调用 ID

        Returns:
            ToolMessage: 链式构建的 ToolMessage 实例
        """
        msg = ToolMessage(name=name, tool_call_id=tool_call_id)
        msg.add_text(f"[{'ERROR' if result.isError else 'SUCCESS'}]")

        for block in result.content:
            if block.type == "text":  # TextContent
                msg.add_text(block.text)

            elif block.type == "image":  # ImageContent
                msg.add_segment(await self._handle_image_block(
                    block.data, block.mimeType
                ))

            elif block.type == "audio":  # AudioContent
                msg.add_segment(await self._handle_audio_block(
                    block.data, block.mimeType
                ))

            elif block.type == "resource":  # EmbeddedResource
                res = block.resource
                uri = str(getattr(res, "uri", "unknown"))
                mime = str(getattr(res, "mimeType", "") or "")
                if isinstance(res, TextResourceContents) and res.text:
                    header = f"[Resource: {uri}]" + (f" ({mime})" if mime else "")
                    msg.add_text(f"{header}\n{res.text}")
                else:
                    # BlobResourceContents
                    blob = (
                        str(getattr(res, "blob", "") or "")
                        if isinstance(res, BlobResourceContents)
                        else ""
                    )
                    if not mime:
                        mime = "application/octet-stream"
                    if blob and mime.startswith("image/"):
                        msg.add_segment(await self._handle_image_block(
                            blob, mime, label=f"Resource({uri})"
                        ))
                    elif blob and mime.startswith("audio/"):
                        msg.add_segment(await self._handle_audio_block(
                            blob, mime, label=f"Resource({uri})"
                        ))
                    else:
                        msg.add_text(f"[Resource: {uri} - {mime}]")

            elif block.type == "resource_link":  # ResourceLink
                uri = str(getattr(block, "uri", "unknown"))
                block_name = str(getattr(block, "name", "") or "")
                description = str(getattr(block, "description", "") or "")
                mime = str(getattr(block, "mimeType", "") or "")
                display = block_name or uri
                lines = [f"[ResourceLink:{display}]"]
                if block_name and uri != block_name:
                    lines.append(f"URI:{uri}")
                if description:
                    lines.append(f"描述:{description}")
                if mime:
                    lines.append(f"类型:{mime}")
                msg.add_text("\n".join(lines))

        if result.structuredContent:
            msg.add_text(str(result.structuredContent))

        msg.refresh_cache()
        
        return msg

    async def _handle_image_block(
        self,
        data: str,
        mime: str,
        label: str = "",
    ) -> MessageSegment:
        """处理一块图片数据:visual_sense 时直传 base64,否则降级为文字描述

        Returns:
            MessageSegment: 处理后的消息段
        """
        if self._visual_sense:
            return ImageBase64Segment(data, mime)
        else:
            tag = f"图片{f'({label})' if label else ''}"
            try:
                desc = await self._media_processor.image_to_text(
                    f"data:{mime};base64,{data}"
                )
                return TextSegment(f"[{tag}描述: {desc}]")
            except Exception as e:
                self.log.warning(f"工具返回{tag}降级描述失败: {e}")
                return TextSegment(f"[{tag}: {mime}]")

    async def _handle_audio_block(
        self,
        data: str,
        mime: str,
        label: str = "",
    ) -> MessageSegment:
        """处理一块音频数据:audio_sense 时直传，否则降级为转文字

        Returns:
            MessageSegment: 处理后的消息段
        """
        if self._audio_sense:
            fmt = mime.split("/")[-1] if "/" in mime else mime
            return AudioSegment(data, fmt)
        else:
            tag = f"音频{f'({label})' if label else ''}"
            try:
                desc = await self._media_processor.audio_to_text(
                    f"data:{mime};base64,{data}"
                )
                return TextSegment(f"[{tag}转文字:{desc}]")
            except Exception as e:
                self.log.warning(f"工具返回{tag}降级转文字失败:{e}")
                return TextSegment(f"[{tag}:{mime}]")

    async def _execute_tool_calls_loop(
        self,
        assistant_message: Dict[str, Any],
    ) -> AsyncGenerator[AgentEvent, None]:
        """执行工具调用循环

        Yields:
            ``ToolCallResultChunk``(流式时)、``TextDeltaChunk``(流式再请求时)
        """
        tool_calls: List[ToolCall] = assistant_message.get("tool_calls", [])

        for _round in range(_MAX_TOOL_ROUNDS):
            self.log.debug(f"工具调用第 {_round + 1} 轮，共 {len(tool_calls)} 个工具")

            #执行本轮所有工具
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name: str = function.get("name", "")
                tool_input_str: str = function.get("arguments", "{}")
                tool_call_id: str = tool_call.get("id", tool_name)

                # 解析参数
                try:
                    arguments: Dict[str, Any] = json.loads(tool_input_str)
                except (json.JSONDecodeError, TypeError):
                    arguments = {}
                    self.log.warning(
                        f"工具 {tool_name} 参数解析失败: {tool_input_str[:200]}"
                    )

                # 触发 on_tool_call 钩子
                await self._trigger_on_tool_call(tool_name, arguments)

                # 执行工具
                tool_msg: ToolMessage
                is_error = False
                try:
                    raw_output = await self._tool_calls_mgr.calls(
                        tool_name,
                        tool_input_str,
                        message_data=self._message_data,
                    )

                    if isinstance(raw_output, CallToolResult):
                        tool_msg = await self._format_mcp_result(
                            raw_output, tool_name, tool_call_id
                        )
                    else:
                        tool_msg = ToolMessage(
                            name=tool_name, 
                            tool_call_id=tool_call_id,
                            content=str(raw_output)
                        )

                except ToolCallsStopIteration:
                    self.log.info(f"模型通过工具 {tool_name} 主动结束工具调用")
                    self._increase_context.append(
                        ToolMessage(
                            name=tool_name,
                            tool_call_id=tool_call_id,
                            content = "结束工具调用"
                        )
                    )
                    # 保持当前 assistant_message 为最后状态
                    self._last_assistant_message = assistant_message
                    return

                except Exception as e:
                    tool_msg = ToolMessage(
                        name=tool_name, 
                        tool_call_id=tool_call_id,
                        content= f"调用工具发生错误\nErrors:{e}"
                    )
                    is_error = True
                    self.log.error(
                        f"工具 {tool_name} 执行失败: {e}", exc_info=True
                    )

                # 触发 on_tool_return 钩子
                await self._trigger_on_tool_return(tool_name, tool_msg.content)

                # 流式:产出 ToolCallResultChunk
                if self.stream:
                    yield tool_call_result(
                        tool_name=tool_name,
                        tool_call_id=tool_call_id,
                        result=tool_msg.content,
                        is_error=is_error,
                        step_index=self._step_index,
                    )

                # 截断过长结果
                if isinstance(tool_msg.content, str):
                    tool_msg.content = tool_msg.content[:_TOOL_OUTPUT_TRUNCATE]
                    tool_msg.refresh_cache()
                elif isinstance(tool_msg.content, list):
                    new_segments = []
                    for seg in tool_msg.content:
                        if isinstance(seg, TextSegment):
                            new_segments.append(TextSegment(seg.text[:_TOOL_OUTPUT_TRUNCATE]))
                        else:
                            new_segments.append(seg)
                    tool_msg.content = new_segments
                    tool_msg.refresh_cache()

                self.log.debug(f"工具 {tool_name} 输出: {str(tool_msg.content)[:300]}...")

                # 追加工具消息到增量上下文
                self._increase_context.append(tool_msg)

            #再次请求 LLM
            try:
                async for event in self._do_llm_request():
                    yield event
            except Exception as e:
                self.log.error(f"工具循环中 LLM 请求失败: {e}")
                raise

            # 更新新一轮的 assistant_message
            assistant_message = self._last_assistant_message

            if next_tool_calls := assistant_message.get("tool_calls"):
                self._increase_context.add_assistant_message(
                    content=assistant_message.get("content"),
                    tool_calls=next_tool_calls,
                    reasoning_content=assistant_message.get(
                        "reasoning_content"
                    ),
                )
                tool_calls = next_tool_calls
                continue
            else:
                self._increase_context.add_assistant_message(
                    content=assistant_message.get("content") or "",
                    reasoning_content=assistant_message.get(
                        "reasoning_content"
                    ),
                    extra_content=assistant_message.get("extra_content"),
                )
                self._last_assistant_message = assistant_message
                return

        self.log.warning(
            f"工具调用循环达到最大轮数 {_MAX_TOOL_ROUNDS}，强制终止"
        )

    @staticmethod
    def _stringify_content(content: str | List[MessageSegment]) -> str:
        """将多模态内容段列表转为纯文本字符串(用于 StepSummary)"""
        if isinstance(content, str):
            return content
        parts: List[str] = []
        for seg in content:
            if isinstance(seg, TextSegment):
                parts.append(seg.text)
            else:
                parts.append(f"[{type(seg).__name__}]")
        return "".join(parts)

    def _build_step_summary(self) -> StepSummary:
        """从增量上下文构建 ``StepSummary``

        提取所有 assistant 消息的 content/reasoning/tool_calls，
        并匹配 tool 消息的结果
        """
        reply_texts: List[str] = []
        reasoning_texts: List[str] = []
        tool_calls_info: List[Dict[str, Any]] = []

        for msg in self._increase_context.messages:
            if isinstance(msg, AssistantMessage):
                if msg.content:
                    reply_texts.append(msg.content)
                if msg.reasoning_content:
                    reasoning_texts.append(msg.reasoning_content)
                if msg.tool_calls:
                    for t in msg.tool_calls:
                        tool_calls_info.append({
                            "id": t.get("id", ""),
                            "name": t.get("function", {}).get("name", ""),
                            "arguments": t.get("function", {}).get(
                                "arguments", ""
                            ),
                        })
            elif isinstance(msg, ToolMessage):
                tid = msg.tool_call_id
                result_content = self._stringify_content(msg.content)
                for tc in tool_calls_info:
                    if tc["id"] == tid:
                        tc["result"] = result_content
                        tc["is_error"] = False
                        break
                else:
                    tool_calls_info.append({
                        "id": tid,
                        "name": msg.name,
                        "result": result_content,
                        "is_error": False,
                    })

        usage = (
            self._last_api_reply.get("usage")
            if self._last_api_reply
            else None
        )

        return step_summary(
            content="".join(reply_texts),
            reasoning_content=(
                "".join(reasoning_texts) if reasoning_texts else None
            ),
            tool_calls=tool_calls_info if tool_calls_info else None,
            usage=usage,
            finish_reason=(
                "tool_calls" if tool_calls_info else "stop"
            ),
            step_index=self._step_index,
            is_final=False,
        )

    async def _execute_step(self) -> AsyncGenerator[AgentEvent, None]:
        """执行单步 LLM 交互(不含钩子触发)

        Yields:
            流式中间事件(TextDelta / ReasoningDelta / ToolCall*)
        """
        self.update_state(AgentState.RUNNING)

        # 重置增量上下文
        self._increase_context = AgentContext()

        async for event in self._do_llm_request():
            yield event

        assistant_message = self._last_assistant_message
        content = self._last_content

        if assistant_message is None:
            raise RuntimeError("LLM 请求未返回有效的 assistant_message")

        if tool_calls := assistant_message.get("tool_calls"):
            self._increase_context.add_assistant_message(
                content=content,
                tool_calls=tool_calls,
                reasoning_content=assistant_message.get("reasoning_content"),
            )

            # 进入工具调用循环
            async for event in self._execute_tool_calls_loop(assistant_message):
                yield event
        else:
            # 普通回复
            self._increase_context.add_assistant_message(
                content=content or "",
                reasoning_content=assistant_message.get("reasoning_content"),
                extra_content=assistant_message.get("extra_content"),
            )

        self.agent_data.context.extend(self._increase_context.messages)

        await self.agent_data.context.record_validity_check()

        self._last_summary = self._build_step_summary()
        self._step_index += 1

        self.update_state(AgentState.IDLE)

    async def step(self) -> AsyncGenerator[AgentEvent, None]:
        """执行单步 LLM 交互，产出流式事件并以 ``StepSummary`` 收尾

        首次调用时触发 ``before_run`` 钩子
        异常时触发 ``on_error`` 钩子并产出 ``AgentError``

        Yields:
            - 流式模式:TextDeltaChunk* → [ToolCallStartChunk → ToolCallResultChunk*]* → StepSummary
            - 非流式模式:StepSummary
        """
        await self._trigger_before_run()

        try:
            async for event in self._execute_step():
                yield event

            summary = self._last_summary
            if summary is not None:
                yield summary
            else:
                yield agent_error(
                    error_message="Step 未产出有效的 StepSummary",
                    step_index=self._step_index,
                )

        except Exception as e:
            self.log.exception(f"Step 执行失败: {e}")
            await self._trigger_on_error(e)
            self.update_state(AgentState.ERROR)
            yield agent_error(
                error_message=str(e),
                exception_type=type(e).__name__,
                step_index=self._step_index,
            )

    async def run(
        self, max_turns: int = 20
    ) -> AsyncGenerator[AgentEvent, None]:
        """完整运行 Agent 多步逻辑，直至任务完结或受阻

        循环调用步逻辑(最多 ``max_turns`` 次),
        聚合各步的 ``StepSummary`` 为 ``RunSummary``

        Args:
            max_turns: 最大步数(防止无限循环)，默认 20

        Yields:
            - 流式模式:各步的流式中间事件 + 每一步的 StepSummary
            - 最终:RunSummary(或 AgentError)
        """
        steps: List[StepSummary] = []
        total_content = ""
        total_reasoning: Optional[str] = None
        total_usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        finish_reason = "completed"

        # 确保 before_run 在 run() 中触发一次(而非 step() 重复触发)
        await self._trigger_before_run()

        try:
            for _turn in range(max_turns):
                # 执行一步(不再触发 before_run)
                async for event in self._execute_step():
                    yield event

                summary = self._last_summary
                if summary is None:
                    finish_reason = "error"
                    yield agent_error(
                        error_message=f"第 {_turn + 1} 步未产出 StepSummary",
                        step_index=self._step_index,
                    )
                    break

                # 标记是否为最终步(临时)，产出 StepSummary
                yield step_summary(
                    content=summary.content,
                    reasoning_content=summary.reasoning_content,
                    tool_calls=summary.tool_calls if summary.tool_calls else None,
                    usage=summary.usage,
                    finish_reason=summary.finish_reason,
                    step_index=summary.step_index,
                    is_final=False,  # 在 RunSummary 中统一标记
                )

                steps.append(summary)
                total_content += summary.content
                if summary.reasoning_content:
                    total_reasoning = (
                        (total_reasoning or "")
                        + summary.reasoning_content
                    )
                if summary.usage:
                    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        total_usage[k] = total_usage.get(k, 0) + summary.usage.get(k, 0)

                if not summary.has_tool_calls:
                    finish_reason = "completed"
                    break
            else:
                # 达到 max_turns
                finish_reason = "max_turns"
                self.log.warning(
                    f"run() 达到最大步数 {max_turns}，强制终止"
                )

            # 构建 RunSummary
            final = run_summary(
                steps=steps,
                total_content=total_content,
                total_reasoning=total_reasoning,
                total_usage=total_usage,
                finish_reason=finish_reason,
            )

            await self._trigger_after_run(final)
            yield final

        except Exception as e:
            self.log.exception(f"Run 执行失败: {e}")
            await self._trigger_on_error(e)
            self.update_state(AgentState.ERROR)

            # 产出部分结果(若有)
            partial = run_summary(
                steps=steps,
                total_content=total_content,
                total_reasoning=total_reasoning,
                total_usage=total_usage,
                finish_reason="error",
            )
            yield agent_error(
                error_message=str(e),
                exception_type=type(e).__name__,
                partial_summary=partial,
                step_index=self._step_index,
            )

        finally:
            self.update_state(AgentState.IDLE)
