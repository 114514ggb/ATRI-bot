import re
from dataclasses import dataclass, field
from logging import Logger
from typing import Any, Dict, List

from mcp.types import BlobResourceContents, CallToolResult, TextResourceContents

from atribot.core.service_container import container
from atribot.core.type.bot_types import MessageEventEnvelope
from atribot.core.type.context_types import Context, MessageBuilder, ToolCallsStopIteration
from atribot.LLMchat.MCP.tool_calls import ToolCalls
from atribot.LLMchat.MCP.tool_model import ToolSet
from atribot.LLMchat.media_processor import MediaProcessor
from atribot.LLMchat.model_api.ai_connection_manager import LLMConnectionManager
from atribot.LLMchat.model_api.model_api_basics import model_api_basics


@dataclass(slots=True)
class GenerationResponse():
    """响应后再更新状态"""

    model: str
    """响应模型名称"""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    """新增上下文"""
    reply_text: List[str] = field(default_factory=list)
    """未合并模型回复的文本"""
    reasoning_content: List[str] = field(default_factory=list)
    """未合并的推理模型的思考过程"""
    metadata: Dict[str, Any] = field(default_factory=dict)
    """可选的额外数据,如果有值可能包含:
        {
            'prompt_tokens': 358,
            'completion_tokens': 78,
            'total_tokens': 436,
            'prompt_tokens_details': {'cached_tokens': 320},
            'prompt_cache_hit_tokens': 320,
            'prompt_cache_miss_tokens': 38
        }
    """
    
    
@dataclass(slots=True)
class GenerationRequest():
    """请求响应"""
    
    model: str
    """模型名称"""
    new_message: str
    """最新一条需要回答的聊天内容"""
    messages: List[Dict[str, Any]]
    """聊天历史"""
    supplier_name:str = ""
    """供应商"""
    model_api:model_api_basics|None = None
    """模型的api实例"""
    prompt: str = ""
    """嵌入上下文的模型输出内容提示"""
    image_url_list: List[str] = None
    """如果有有的话会加入响应"""
    system_review:bool = False
    """prompt嵌入时是否单独使用system而不是采用直接拼接"""
    tool_json: ToolSet | None = None
    """可供模型调用工具集合"""
    parameter: Dict = None
    """模型参数"""
    generation_response: GenerationResponse|None = None
    """
    从上次错误继承来未完成返回值\n
    如果是调用工具时出现api响应错误时重试的时候这个会有值\n
    如果是初始请求则为None
    """
    message_data: MessageEventEnvelope = None
    """触发此次请求的事件对象,工具调用时自动注入到声明了 message_data 参数的本地工具函数"""
    visual_sense: bool = False
    """当前模型是否支持图像输入，工具返回图片时决定直接传图还是降级为文字描述"""
    audio_sense: bool = False
    """当前模型是否支持音频输入，工具返回音频时决定直接传递还是降级转文字"""

@dataclass(slots=True)
class GenerationRequestSimplify():
    """请求响应"""
    
    model: str
    """模型名称"""
    messages: List[Dict[str, Any]]
    """模型聊天的历史上下文"""
    supplier_name:str = ""
    """供应商"""
    increment_messages:List[Dict[str, Any]]|None = None
    """增量上下文""" 
    model_api:model_api_basics|None = None
    """模型的api实例"""
    tool_json: ToolSet | None = None
    """可供模型调用工具集合"""
    parameter: Dict = None
    """模型参数"""
    generation_response: GenerationResponse|None = None
    """
    从上次错误继承来未完成返回值\n
    如果是调用工具时出现api响应错误时重试的时候这个会有值\n
    如果是初始请求则为None
    """
    message_data: MessageEventEnvelope = None
    """触发此次请求的事件对象,工具调用时自动注入到声明了 message_data 参数的本地工具函数"""
    visual_sense: bool = False
    """当前模型是否支持图像输入，工具返回图片时决定直接传图还是降级为文字描述"""
    audio_sense: bool = False
    """当前模型是否支持音频输入，工具返回音频时决定直接传递还是降级转文字"""

class LLMSRequestFailed(Exception):
    """LLM请求失败异常
    
    可能是网络问题，也可能是请求参数问题
    """
    
    def __init__(
        self, 
        exception: Exception, 
        response: GenerationResponse = None,
        custom_message: str = ""
    ):
        """
        Args:
            exception: 原始异常对象
            response: 执行到一半的返回值
            custom_message: 自定义错误消息，如不提供则使用默认格式
        """
        self.response = response
        self.exception = exception
        self.custom_message = custom_message
        
        if custom_message:
            display_message = custom_message
        else:
            display_message = f"LLM请求失败: {str(exception)}"
            
        super().__init__(display_message)
    
    def __str__(self):
        """字符串表示，包含详细上下文信息"""
        base_message = super().__str__()
        return base_message
    
    @property
    def original_exception_type(self) -> str:
        """获取原始异常类型"""
        return type(self.exception).__name__
    
    def get_response(self) -> GenerationResponse|None:
        """获取中断的状态信息属性"""
        return self.response


class LLMCoordinator():
    """获取LLM响应的主类,面向openAI的格式"""
    
    def __init__(self):
        self.supplier = container.get_by_type(LLMConnectionManager)
        self.tool_management = container.get_by_type(ToolCalls)
        self.log: Logger = container.get_by_type(Logger).getChild("LLMCoord")
        self._media_processor = container.get_by_type(MediaProcessor)
        
    async def step(self, request:GenerationRequest)->GenerationResponse:
        """对于GenerationRequest的主处理函数

        Args:
            request (GenerationRequest): 输入

        Returns:
            GenerationResponse: 输出
        """ 
        increase_context = self.get_init_context(request)
            
        model_api = request.model_api or (self.supplier.get_filtration_connection(
            supplier_name=request.supplier_name,
            model_name=request.model,
        )[0]).connection_object

        #中断继续
        if request.generation_response is not None:
            return await self.resume_step(request,model_api,increase_context)
                
        api_reply, assistant_message, content = await self._get_assistant_message_with_retry(
            request = request,
            increase_context  = increase_context,
            model_api  = model_api
        )
        return await self._handle_assistant_message(
            request = request,
            api_reply = api_reply,
            assistant_message = assistant_message,
            content = content,
            increase_context = increase_context,
            model_api = model_api
        )
        

    async def run(self, request:GenerationRequestSimplify)->GenerationResponse:
        """对于GenerationRequest的主处理函数,运行后产生结果,中间会处理工具掉用

        Args:
            request (GenerationRequest): 输入

        Returns:
            GenerationResponse: 输出
        """ 
        increase_context = Context(messages = request.increment_messages[:])#浅拷贝一个应该够用了
        
        model_api = request.model_api or (self.supplier.get_filtration_connection(
            supplier_name=request.supplier_name,
            model_name=request.model,
        )[0]).connection_object

        #中断继续
        if request.generation_response is not None:
            return await self.resume_step(request,model_api,increase_context)
        
        api_reply, assistant_message, content = await self._get_assistant_message_with_retry(
            request = request,
            increase_context  = increase_context,
            model_api  = model_api
        )
        return await self._handle_assistant_message(
            request = request,
            api_reply = api_reply,
            assistant_message = assistant_message,
            content = content,
            increase_context = increase_context,
            model_api = model_api
        )

    
    async def resume_step(
        self, 
        request :GenerationRequest|GenerationRequestSimplify, 
        model_api :model_api_basics, 
        increase_context: Context
    )->GenerationResponse:
        """从中断继续请求

        Args:
            request (GenerationRequest): 输入
            model_api (model_api_basics): 模型api实例
            increase_context (Context): 新增上下文

        Returns:
            GenerationResponse: 返回
        """
        self.log.debug("从中断继续请求!")
        
        for msg in request.generation_response.messages: 
            if msg['role'] in ['assistant','tool']:
                increase_context.messages.append(msg)
        
        api_reply,assistant_message, content = await self._get_assistant_message_with_retry(
            request = request,
            increase_context  = increase_context,
            model_api  = model_api
        )
        return await self._handle_assistant_message(
            request = request,
            api_reply = api_reply,
            assistant_message = assistant_message,
            content = content,
            increase_context = increase_context,
            model_api = model_api
        )


    async def _handle_assistant_message(
        self,
        request: GenerationRequest|GenerationRequestSimplify,
        api_reply: Dict[str, Any],
        assistant_message: Dict[str, Any],
        content: str|None,
        increase_context: Context,
        model_api: model_api_basics
    ) -> GenerationResponse:
        """统一处理助手消息中的工具调用与普通回复分支"""
        if tool_calls := assistant_message.get('tool_calls'):
            increase_context.add_assistant_tool_message(
                content,
                tool_calls = tool_calls,
                reasoning_content = assistant_message.get("reasoning_content")
            )

            return await self.tool_calls_while(
                request = request,
                tool_calls = tool_calls,
                assistant_message = assistant_message,
                increase_context = increase_context,
                model_api = model_api
            )
            
        # increase_context.messages.append(assistant_message)
        increase_context.add_assistant_message(
            content = assistant_message.get("content",""),
            reasoning_content = assistant_message.get("reasoning_content"),
            extra_content = assistant_message.get("extra_content")
         )
        
        return self._update_response(
            GenerationResponse(
                model = request.model,
                messages = increase_context.messages,
                metadata = api_reply.get("usage", {})
            ),
            assistant_message
        )
        
       
    async def tool_calls_while(
        self, 
        request:GenerationRequest|GenerationRequestSimplify, 
        tool_calls: list,
        assistant_message:dict, 
        increase_context:Context, 
        model_api:model_api_basics
    )->GenerationResponse:
        """处理模型有工具调用的情况

        Args:
            request (GenerationRequest): 输入
            tool_calls (list): 调用的工具list
            assistant_message (dict): 模型上一次返回
            increase_context (Context): 新增的上下文部分
            model_api (model_api_basics): api响应实例

        Returns:
            GenerationResponse: 返回
        """
        self.log.debug("模型进入工具调用!")
        
        response = request.generation_response or GenerationResponse(model = request.model)
        
        for _ in range(10):#防止无限循环调用
            
            self._update_response(response, assistant_message)

            for tool_call in tool_calls:#可能一次里面调用多少工具 
                
                try:
                    function = tool_call['function']
                    tool_name = function['name']
                    tool_input = function['arguments']

                    tool_output: CallToolResult | Any = await self.tool_management.calls(tool_name, tool_input, request.message_data)
                    if isinstance(tool_output, CallToolResult):
                        tool_output = await self._format_mcp_result_rich(tool_output, request.visual_sense, request.audio_sense)
                    else:
                        tool_output = str(tool_output)
                    
                except ToolCallsStopIteration:
                    increase_context.add_tool_message(tool_name,tool_call['id'],tool_output)
                    self.log.info("模型主动结束工具调用!")
                    response.messages = increase_context.messages
                    return response
                    
                except Exception as e:
                    text = f"调用工具发生错误。\nErrors:{e}"
                    self.log.error(text,exc_info=True)
                    tool_output = text

                self.log.debug(f"工具调用输出:{tool_output}")
                
                # 截断防止有的工具返回过长的结果
                if isinstance(tool_output, str):
                    tool_output = tool_output[:20000]
                elif isinstance(tool_output, list):
                    for part in tool_output:
                        if part.get("type") == "text":
                            part["text"] = part["text"][:20000]

                increase_context.add_tool_message(
                    tool_name,
                    tool_call['id'],
                    tool_output,
                )
              
            try:
                api_reply,assistant_message, content = await self._get_assistant_message_with_retry(
                    request = request,
                    increase_context  = increase_context,
                    model_api  = model_api
                )
            except Exception as e:
                response.messages = increase_context.messages
                raise LLMSRequestFailed(e, response)
            
            if usage := api_reply.get("usage"):
                response.metadata = usage
                
            if tool_calls := assistant_message.get('tool_calls'):
                increase_context.add_assistant_tool_message(
                    content,
                    tool_calls,
                    reasoning_content = assistant_message.get("reasoning_content")
                )
            else:
                increase_context.add_assistant_message(
                    content = content,
                    reasoning_content = assistant_message.get("reasoning_content"),
                    extra_content = assistant_message.get("extra_content")
                )
                break
        
        self.log.debug("工具调用结束!")
        
        response.messages = increase_context.messages
        
        return self._update_response(response, assistant_message)
    
    @staticmethod
    def get_init_context(request:GenerationRequest)->Context:
        """获取初始上下文"""
        increase_context = Context()
            
        if request.system_review:
            increase_context.add_system_message(request.prompt)
            base_message = request.new_message
        else:
            base_message = request.prompt + request.new_message

        if request.image_url_list:
            increase_context.add_img_message("user", base_message, request.image_url_list)
        else:
            increase_context.add_user_message(base_message)
        
        return increase_context

    def _update_response(self, response: GenerationResponse, assistant_message: Dict) -> GenerationResponse:
        """更新response"""
        
        if explicit_reasoning := assistant_message.get("reasoning_content"):
            response.reasoning_content.append(explicit_reasoning)
            
        if cleaned_content := assistant_message.get("content") or "":
            response.reply_text.append(cleaned_content)
            
        return response

    
    async def _format_mcp_result_rich(
        self,
        result: CallToolResult,
        visual_sense: bool,
        audio_sense: bool = False,
    ) -> str | list:
        """将 MCP 工具执行结果格式化，支持全类型 ContentBlock 多模态处理

        Args:
            result: MCP 工具返回值
            visual_sense: 当前模型是否支持图像输入
            audio_sense: 当前模型是否支持音频输入

        Returns:
            纯文本(str) 或 多模态内容列表(list)
        """
        builder = MessageBuilder("tool")
        builder.add_text(f"[{'ERROR' if result.isError else 'SUCCESS'}]")

        for block in result.content: 
            if block.type == "text":#TextContent
                builder.add_text(block.text)

            elif block.type == "image":#ImageContent
                await self._handle_image_block(block.data, block.mimeType, visual_sense, builder)

            elif block.type == "audio":#AudioContent
                await self._handle_audio_block(block.data, block.mimeType, audio_sense, builder)

            elif block.type == "resource":  # EmbeddedResource
                res = block.resource
                uri = str(getattr(res, "uri", "unknown"))
                mime = str(getattr(res, "mimeType", "") or "")
                if isinstance(res, TextResourceContents) and res.text:
                    header = f"[Resource: {uri}]" + (f" ({mime})" if mime else "")
                    builder.add_text(f"{header}\n{res.text}")
                else:
                    # BlobResourceContents
                    blob = str(getattr(res, "blob", "") or "") if isinstance(res, BlobResourceContents) else ""
                    if not mime:
                        mime = "application/octet-stream"
                    if blob and mime.startswith("image/"):
                        await self._handle_image_block(blob, mime, visual_sense, builder, label=f"Resource({uri})")
                    elif blob and mime.startswith("audio/"):
                        await self._handle_audio_block(blob, mime, audio_sense, builder, label=f"Resource({uri})")
                    else:
                        builder.add_text(f"[Resource: {uri} - {mime}]")

            elif block.type == "resource_link":  # ResourceLink
                uri = str(getattr(block, "uri", "unknown"))
                name = str(getattr(block, "name", "") or "")
                description = str(getattr(block, "description", "") or "")
                mime = str(getattr(block, "mimeType", "") or "")
                display = name or uri
                lines = [f"[ResourceLink:{display}]"]
                if name and uri != name:
                    lines.append(f"URI:{uri}")
                if description:
                    lines.append(f"描述:{description}")
                if mime:
                    lines.append(f"类型:{mime}")
                builder.add_text("\n".join(lines))

        if result.structuredContent:
            builder.add_text(str(result.structuredContent))

        return builder.build_content()

    async def _handle_image_block(
        self,
        data: str,
        mime: str,
        visual_sense: bool,
        builder: MessageBuilder,
        label: str = "",
    ) -> None:
        """处理一块图片数据:visual_sense 时直传，否则降级为文字描述"""
        if visual_sense:
            builder.add_image_base64(data, mime)
        else:
            tag = f"图片{f'({label})' if label else ''}"
            try:
                desc = await self._media_processor.image_to_text(f"data:{mime};base64,{data}")
                builder.add_text(f"[{tag}描述: {desc}]")
            except Exception as e:
                self.log.warning(f"工具返回{tag}降级描述失败: {e}")
                builder.add_text(f"[{tag}: {mime}]")

    async def _handle_audio_block(
        self,
        data: str,
        mime: str,
        audio_sense: bool,
        builder: MessageBuilder,
        label: str = "",
    ) -> None:
        """处理一块音频数据"""
        if audio_sense:
            fmt = mime.split("/")[-1] if "/" in mime else mime
            builder.add_audio(data, fmt)
        else:
            tag = f"音频{f'({label})' if label else ''}"
            try:
                desc = await self._media_processor.audio_to_text(f"data:{mime};base64,{data}")
                builder.add_text(f"[{tag}转文字:{desc}]")
            except Exception as e:
                self.log.warning(f"工具返回{tag}降级转文字失败:{e}")
                builder.add_text(f"[{tag}:{mime}]")

    @staticmethod
    def format_mcp_result(result: CallToolResult) -> str:
        """将 MCP 工具执行结果格式化为纯文本字符串（文本降级版本）

        Args:
            result: MCP 工具执行结果

        Returns:
            包含格式化状态和内容的字符串
        """
        parts = [f"[{'ERROR' if result.isError else 'SUCCESS'}]"]

        for block in result.content:
            if block.type == "text":
                parts.append(block.text)

            elif block.type in ("image", "audio"):
                parts.append(f"[{block.type.capitalize()}: {block.mimeType}]")

            elif block.type == "resource":
                res = block.resource
                uri = getattr(res, "uri", "unknown")
                if hasattr(res, "text") and res.text:
                    parts.append(f"[Resource: {uri}]\n{res.text}")
                else:
                    mime = getattr(res, "mimeType", "application/octet-stream")
                    parts.append(f"[Resource: {uri} - {mime}]")

            elif block.type == "resource_link":
                parts.append(f"[Link: {getattr(block, 'uri', 'unknown')}]")

        if result.structuredContent:
            parts.append(str(result.structuredContent))

        return "\n".join(parts)
    

    async def _get_assistant_message_with_retry(
        self,
        request: GenerationRequest|GenerationRequestSimplify,
        increase_context: Context,
        model_api: model_api_basics,
        max_retries: int = 5
    ) -> tuple[Dict,Dict,str|None]:
        """获取模型回复，包含重试机制
        
        Args:
            request (GenerationRequest): 生成请求
            increase_context (Context): 上下文
            model_api (model_api_basics): 模型API实例
            max_retries (int): 最大重试次数
        
        Returns:
            tuple[Dict,Dict,str|None]: 响应原始消息体还有整个助手消息体和助手文本(如果有的话)组成的Tuple
        
        Raises:
            ValueError: 当空回复次数超过阈值时抛出
        """
        for _ in range(max_retries):       
            api_reply:Dict = await self.get_chat_json(
                request = request,
                messages = increase_context.get_messages(),
                model_api = model_api
            )
            
            self.log.debug(f"模型返回:{api_reply}")
            
            assistant_message:Dict = api_reply['choices'][0]['message']
            content = assistant_message.get('content')
            
            if content:
                return api_reply,assistant_message, content
            elif assistant_message.get("tool_calls"):
                return api_reply,assistant_message, None
        
        raise ValueError(f"在{max_retries}次尝试后仍未能获取有效回复")
    
    
    @staticmethod
    def extract_thought(text):
        """
        提取字符串中被<thought></thought>标签包裹的内容，并返回去掉标签后的文本
        
        Args:
            text: 输入的文本字符串
            
        Returns:
            tuple: (thought_content, cleaned_text)
                - thought_content: 提取的thought内容，没有则返回空字符串
                - cleaned_text: 去掉<thought></thought>标签后的文本
        """
        if match:= re.search(r'<thought>(.*?)</thought>', text, re.DOTALL):
            thought_content = match.group(1)
            cleaned_text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL)
            return thought_content, cleaned_text
        else:
            return "", text
    
    async def get_chat_json(
        self,
        request:GenerationRequest|GenerationRequestSimplify, 
        messages:List[Dict[str, Any]], 
        model_api:model_api_basics
    )->Dict:
        """发起向api的请求

        Args:
            request (GenerationRequest | GenerationRequestSimplify): _description_
            messages (List[Dict[str, Any]]): 消息的新增部分
            model_api (model_api_basics): _description_

        Returns:
            Dict: 请求回的json
        """
        tools = (
            self.tool_management.get_openai(toolset=request.tool_json)
            if request.tool_json is not None
            else None
        )
        if request.parameter:
            parameter = {
                "messages": request.messages + messages, 
                "tools":  tools,
                **request.parameter
            }
            if request.parameter.get('stream'):
                return await model_api.generate_json_ample_stream(
                    model = request.model,
                    remainder = parameter
                )
            
            return await model_api.generate_json_ample(
                model = request.model,
                remainder = parameter
            )
        else:
            return await model_api.generate_text_tools(
                model = request.model,
                messages = request.messages + messages, 
                tools = tools
            )