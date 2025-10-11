from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.LLMchat.model_api.model_api_basics import model_api_basics
from atribot.core.service_container import container
from atribot.LLMchat.model_tools import tool_calls
from atribot.core.types import (
    ToolCallsStopIteration,
    Context
)
from typing import Dict, List, Any
from dataclasses import dataclass
from logging import Logger
import re

    
    
    
@dataclass
class GenerationResponse():
    """响应后再更新状态"""
    
    messages: List[Dict[str, Any]] = None
    """新增上下文"""
    reply_text: str = ""
    """合并后的模型回复的文本"""
    reasoning_content: str = ""
    """合并后的推理模型的思考过程"""
    metadata: Dict[str, Any] = None
    """基本信息"""


@dataclass
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
    tool_json: List[Dict] = None
    """可供模型调用的json"""
    parameter: Dict = None
    """模型参数"""
    generation_response: GenerationResponse|None = None
    """
    从上次错误继承来未完成返回值\n
    如果是调用工具时出现api响应错误时重试的时候这个会有值\n
    如果是初始请求则为None
    """

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
    
    def get_response(self) -> List[Dict[str, Any]]|None:
        """获取中断的状态信息属性"""
        return self.response


class large_language_model_supervisor():
    """LLM响应的主类"""
    
    def __init__(self):
        self.supplier:ai_connection_manager = container.get("LLMSupplier")
        self.logger:Logger = container.get("log")
        self.config = container.get("config")
        self.tool_management = tool_calls()
        
        
    async def step(self, request:GenerationRequest)->GenerationResponse:
        """主处理函数

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

        if request.generation_response is not None:
            self.logger.debug("从中断继续请求!")
            return self.resume_step(request,model_api,increase_context)
                
        api_reply:Dict = await self.get_chat_json(
            request = request,
            messages = increase_context.get_messages(),
            model_api = model_api
        )
        
        self.logger.debug(f"模型返回:{api_reply}")
        
        assistant_message:Dict = api_reply['choices'][0]['message']
        
        if content := assistant_message.get('content'):
            pass
        else:
            content = ""
        
        if 'tool_calls' not in assistant_message or assistant_message['tool_calls'] is None:
            #没有tool调用提前返回
            
            increase_context.add_assistant_message(content)
            return  self._update_response(
                GenerationResponse(
                    messages = increase_context.messages
                ), 
                assistant_message
            )
        
        
        increase_context.add_assistant_tool_message(
            content,
            assistant_message['tool_calls']
        )
        
        return await self.tool_calls_while(
            request = request,
            assistant_message = assistant_message,
            increase_context = increase_context,
            model_api = model_api
        )
        
        
    async def tool_calls_while(self, request:GenerationRequest, assistant_message:dict, increase_context:Context, model_api:model_api_basics)->GenerationResponse:
        """处理模型有工具调用的情况

        Args:
            request (GenerationRequest): 输入
            assistant_message (dict): 模型上一次返回
            increase_context (Context): 新增的上下文部分
            model_api (model_api_basics): api响应实例

        Returns:
            GenerationResponse: 返回
        """
        self.logger.debug("模型进入工具调用!")
        
        response = request.generation_response or GenerationResponse()
        
        for _ in range(8):#防止无限循环调用
            
            self._update_response(response, assistant_message)

            for tool_call in assistant_message['tool_calls']:#可能一次里面调用多少工具
                
                try:
                    function = tool_call['function']
                    tool_name = function['name']
                    tool_input = function['arguments']
                    tool_output = ""

                    tool_output = str(await self.tool_management.calls(tool_name,tool_input))
                    
                except ToolCallsStopIteration:
                    increase_context.add_tool_message(tool_output,tool_call['id'])
                    self.logger.info("模型主动结束工具调用!")
                    response.messages = increase_context.messages
                    return response
                    
                except Exception as e:
                    text = f"调用工具发生错误。\nErrors:{e}"
                    self.logger.error(text)
                    tool_output = text

                self.logger.debug(f"工具调用输出:{tool_output}")
                
                increase_context.add_tool_message(
                    tool_output[:20000],#截断防止有的工具返回过长的结果
                    tool_call['id']
                )
            
            try:
                api_reply = await self.get_chat_json(
                    request = request,
                    messages = increase_context.get_messages(),
                    model_api = model_api
                )
            except Exception as e:
                response.messages = increase_context.messages
                raise LLMSRequestFailed(e, response)
            
            self.logger.debug(f"工具调用后模型返回:{api_reply}")
            
            assistant_message:Dict = api_reply['choices'][0]['message']

            if content := assistant_message.get('content'):
                pass
            else:
                content = ""
            
            if 'tool_calls' not in assistant_message or assistant_message['tool_calls'] is None:
                increase_context.add_assistant_tool_message(content)
                break
            
            increase_context.add_assistant_tool_message(
                content,
                assistant_message['tool_calls']
            )
        
        response.messages = increase_context.messages
        
        return self._update_response(response, assistant_message)
    
    async def resume_step(
        self, 
        request :GenerationRequest, 
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
        response = request.generation_response
        
        for msg in response.messages:
            if msg['role'] in ['assistant','tool']:
                increase_context.messages.append(msg)
                
        api_reply:Dict = await self.get_chat_json(
            request = request,
            messages = increase_context.get_messages(),
            model_api = model_api
        )
        
        self.logger.debug(f"模型返回:{api_reply}")
        
        assistant_message:Dict = api_reply['choices'][0]['message']
        
        if content := assistant_message.get('content'):
            pass
        else:
            content = ""
        
        if 'tool_calls' not in assistant_message or assistant_message['tool_calls'] is None:
            
            self._update_response(response, assistant_message)
            increase_context.add_assistant_message(content)
            response.messages = increase_context.messages
            return response
        
        increase_context.add_assistant_tool_message(
            content,
            assistant_message['tool_calls']
        )
        
        return await self.tool_calls_while(
            request = request,
            assistant_message = assistant_message,
            increase_context = increase_context,
            model_api = model_api
        )
    
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
            
            
    def _update_response(self, response:GenerationResponse ,assistant_message:Dict)->GenerationResponse:
        """更新response"""
        content:str = assistant_message.get("content")
        content = content if content else ""
        
        if content.startswith("<thought>"):
            reasoning_content ,content= self.extract_thought(content)
            response.reasoning_content += assistant_message.get("reasoning_content",reasoning_content)
            response.reply_text += content
            return response
        
        
        response.reasoning_content += assistant_message.get("reasoning_content","")
        response.reply_text += content
        
        return response
    
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
        match = re.search(r'<thought>(.*?)</thought>', text, re.DOTALL)
        
        if match:
            thought_content = match.group(1)
            cleaned_text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL)
            return thought_content, cleaned_text
        else:
            return "", text
    
    @staticmethod
    async def get_chat_json(request:GenerationRequest, messages:List[Dict[str, Any]], model_api:model_api_basics)->Dict:
        """发起向api的请求"""
        if request.parameter:
            parameter = {
                "messages": request.messages + messages,
                "tools":  request.tool_json,
            } | request.parameter
            
            return await model_api.generate_json_ample(
                model = request.model,
                remainder = parameter
            )
        else:
            return await model_api.generate_text_tools(
                model = request.model,
                messages = request.messages+messages,
                tools = request.tool_json
            )