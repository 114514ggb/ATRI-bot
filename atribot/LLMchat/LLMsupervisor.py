from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.LLMchat.model_api.model_api_basics import model_api_basics
from atribot.core.service_container import container
from atribot.LLMchat.model_tools import tool_calls
from atribot.core.types import Context
from typing import Dict, List, Any
from dataclasses import dataclass
from logging import Logger



    
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
    model_api:model_api_basics = None
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
    
    
    
@dataclass
class GenerationResponse():
    """响应后再更新状态"""
    
    messages: List[Dict[str, Any]]
    """新增上下文"""
    reply_text: str
    """合并后的模型回复的文本"""
    reasoning_content: str = ""
    """推理模型的思考过程"""
    metadata: Dict[str, Any] = None
    """基本信息"""


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
        
        model_api = request.model_api or (self.supplier.get_filtration_connection(
            supplier_name=request.supplier_name,
            model_name=request.model
        )[0]).connection_object

        assistant_message:Dict = (await self.get_chat_json(
            request = request,
            messages = request.messages + increase_context.get_messages(),
            model_api = model_api
        ))['choices'][0]['message']
        
        if 'tool_calls' not in assistant_message or assistant_message['tool_calls'] is None:
            #没有tool调用提前返回
            return GenerationResponse(
                messages = increase_context,
                reply_text = assistant_message['content'],
                reasoning_content = assistant_message.get("reasoning_content","")
            )
            
        
        increase_context.append(assistant_message)
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
        
        reasoning_content = ""
        """推理模型的思考"""
        reply = ""
        """回复的文本部分"""
        
        for _ in range(5):#防止无限循环调用
            
            if content := assistant_message.get('content', ''):
                reply += content
                
            if content := assistant_message.get("reasoning_content",""):
                reasoning_content += content
                
            for tool_call in assistant_message['tool_calls']:#可能一次里面调用多少工具
                
                try:
                    function = tool_call['function']
                    tool_name = function['name']
                    tool_input = function['arguments']
                    tool_output = ""

                    tool_output = str(await self.tool_management.calls(tool_name,tool_input))

                except Exception as e:
                    text = f"调用工具发生错误。\nErrors:{e}"
                    self.logger.error(text)
                    tool_output = text
                    
            increase_context.add_tool_message(
                tool_output[:20000],#截断防止有的工具返回过长的结果
                tool_call['id']
            )
            
            if tool_output == "{'tool_calls_end': '已退出循环'}":
                return GenerationResponse(
                    messages = increase_context,
                    reply_text = reply,
                    reasoning_content = reasoning_content
                )
            
            assistant_message = (await self.get_chat_json(
                request = request,
                messages = request.messages + increase_context.get_messages(),
                model_api = model_api
            ))['choices'][0]['message']
            
            increase_context.append(assistant_message)
            
            if 'tool_calls' not in assistant_message or assistant_message ['tool_calls'] is None:
                return GenerationResponse(
                    messages = increase_context,
                    reply_text = reply + assistant_message.get('content', ''),
                    reasoning_content = reasoning_content
                )
    
    
    @staticmethod
    async def get_chat_json(request:GenerationRequest, messages:List[Dict[str, Any]], model_api:model_api_basics)->Dict:
        if request.parameter:
            parameter = {
                "messages": messages,
                "tools":  request.tool_json,
            } | request.parameter
            
            return await model_api.generate_json_ample(
                model = request.model,
                remainder = parameter
            )
        else:
            return await model_api.generate_text_tools(
                model = request.model,
                messages = messages,
                tools = request.tool_json
            )