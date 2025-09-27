from atribot.LLMchat.model_api.ai_connection_manager import ai_connection_manager
from atribot.LLMchat.model_api.model_api_basics import model_api_basics
from atribot.core.service_container import container
from atribot.LLMchat.model_tools import tool_calls
from atribot.core.types import Context,ToolCallsStopIteration
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
            model_name=request.model,
        )[0]).connection_object

        api_reply:Dict = await self.get_chat_json(
            request = request,
            messages = request.messages + increase_context.get_messages(),
            model_api = model_api
        )
        
        self.logger.debug(f"模型返回:{api_reply}")
        
        assistant_message:Dict = api_reply['choices'][0]['message']
        
        if 'tool_calls' not in assistant_message or assistant_message['tool_calls'] is None:
            #没有tool调用提前返回
            
            increase_context.add_assistant_message(assistant_message.get('content',""))
            return  self._update_response(
                GenerationResponse(messages = increase_context.messages), 
                assistant_message
            )
            
        increase_context.add_assistant_tool_message(
            assistant_message.get('content',""),
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
        
        response = GenerationResponse()
        
        for _ in range(8):#防止无限循环调用
            
            response = self._update_response(response, assistant_message)

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
            
            api_reply = await self.get_chat_json(
                request = request,
                messages = request.messages + increase_context.get_messages(),
                model_api = model_api
            )
            
            self.logger.debug(f"工具调用后模型返回:{api_reply}")
            
            assistant_message:Dict = api_reply['choices'][0]['message']
        
            if 'tool_calls' not in assistant_message or assistant_message['tool_calls'] is None:
                increase_context.add_assistant_tool_message(assistant_message.get('content',""))
                break
            
            increase_context.add_assistant_tool_message(
                assistant_message.get('content',""),
                assistant_message['tool_calls']
            )
        
        response.messages = increase_context.messages
        
        return self._update_response(response, assistant_message)
    
    
    
    @staticmethod
    def _update_response(response:GenerationResponse ,assistant_message:Dict)->GenerationResponse:
        """更新response

        Args:
            response (GenerationResponse): 原response
            assistant_message (Dict): api返回消息

        Returns:
            GenerationResponse: 更新后的response
        """
        response.reply_text += assistant_message.get("content")
        response.reasoning_content += assistant_message.get("reasoningcontent","")
        
        return response
    
    @staticmethod
    async def get_chat_json(request:GenerationRequest, messages:List[Dict[str, Any]], model_api:model_api_basics)->Dict:
        """发起向api的请求"""
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