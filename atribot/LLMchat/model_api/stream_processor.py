from typing import Callable, AsyncGenerator, Dict




class StreamProcessor:
    """流式响应处理器基类"""
    
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        
        self.handlers: list[Callable[[dict], bool]] = [
            self._handle_reasoning,
            self._handle_content,
            self._handle_tool_calls,
        ]

    @staticmethod
    def _create_initial_state() -> dict:
        """创建初始状态"""
        return {
            "reasoning_content": "",
            "content": "",
            "tool_calls": [],
            "usage": None,
            "extra_content" : None,
        }

    @staticmethod
    def _handle_reasoning(delta: dict, state: dict) -> bool:
        """阶段一：处理 reasoning_content"""
        if "reasoning_content" in delta:
            state["reasoning_content"] += delta["reasoning_content"]
            return False
        return True

    @staticmethod
    def _handle_content(delta: dict, state: dict) -> bool:
        """阶段二：处理普通 content"""
        if "content" in delta and delta["content"]:
            state["content"] += delta["content"]
            return False
        return True

    @staticmethod
    def _handle_tool_calls(delta: dict, state: dict) -> bool:
        """阶段三：处理 tool_calls"""
        delta_tool_calls = delta.get("tool_calls")
        if not delta_tool_calls:
            return True
        
        tool_calls: list = state["tool_calls"]
        
        for tool_call_delta in delta_tool_calls:
            index:int = tool_call_delta.get("index")
            current_len = len(tool_calls)
            
            if index is None or index == current_len:
                new_tool_call = {
                    "id": "",
                    "type": "function",
                    "function": {
                        "name": "",
                        "arguments": ""
                    }
                }
                if index is not None:
                    new_tool_call["index"] = index
                    
                tool_calls.append(new_tool_call)
                current = new_tool_call
                
            elif index < current_len:
                current = tool_calls[index]
            else:
                rows_to_add = index - current_len + 1
                for i in range(rows_to_add):
                    tool_calls.append({
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                        "index": current_len + i
                    })
                current = tool_calls[index]

            if "id" in tool_call_delta:
                current["id"] = tool_call_delta["id"]
            
            if "type" in tool_call_delta:
                current["type"] = tool_call_delta["type"]
            
            if "function" in tool_call_delta:
                delta_func = tool_call_delta["function"]
                current_func = current["function"]
                
                if "arguments" in delta_func:
                    current_func["arguments"] += delta_func["arguments"]
                
                if "name" in delta_func:
                    current_func["name"] += delta_func["name"]
            
            #谷歌额外兼容
            if "extra_content" in tool_call_delta:
                 current["extra_content"] = tool_call_delta["extra_content"]
        
        return False
    
    
    async def process_stream(self, async_generator:AsyncGenerator[Dict, None]) -> dict:
        """使用迭代器处理流式数据，接收完后返回兼容的格式

        Args:
            async_generator (AsyncGenerator[Dict, None]): 异步迭代器

        Returns:
            dict: 兼容的非流式格式
        """
        
        state = self._create_initial_state()
        handler_iter = iter(self.handlers)
        current_handler = next(handler_iter, None)
        
        async for chunk in async_generator:

            # if current_handler is None:
            #     break
            
            for choice in chunk.get("choices", []):

                while current_handler is not None:
                    
                    if current_handler(choice.get("delta", {}), state):#返回的是是否要切换
                        current_handler = next(handler_iter, None)
                    else:
                        break
        
        message = {
            "role": "assistant"
        }
        
        if state["reasoning_content"]:
            message["reasoning_content"] = state["reasoning_content"]
        
        if state["content"]:
            message["content"] = state["content"]

        if state["tool_calls"]:
            message["tool_calls"] = state["tool_calls"]
        
        #谷歌兼容
        if extra_content := chunk["choices"][0]["delta"].get("extra_content"):
            message["extra_content"] = extra_content
        
        result = {
            "choices": [{
                "index": 0,
                "message": message,
                # "finish_reason": chunk['choices'][0]["finish_reason"]
            }]
        }
        
        if finish_reason := chunk['choices'][0].get("finish_reason"):
            result["choices"][0]["finish_reason"] = finish_reason
        
        if "usage" in chunk:
            result["usage"] = chunk["usage"]
        
        return result
    

    @staticmethod
    async def process_stream_simple(async_generator: AsyncGenerator[Dict, None]) -> dict:
        """简化的流式响应处理器，支持正确处理多字节字符
        
        Args:
            async_generator: 异步生成器,产出包含choices的字典
            
        Returns:
            dict: 处理后的完整响应
        """
        reasoning_content = ""
        content = ""
        tool_calls = []
        
        async for chunk in async_generator:
            choices = chunk.get("choices")
            
            if not choices:
                continue
                
            delta = choices[0].get("delta", {})
            
            if "reasoning_content" in delta:
                reasoning_content += delta["reasoning_content"]
            
            if delta.get("content"):
                content += delta["content"]
            
            if delta_tool_calls := delta.get("tool_calls"):
                for tool_call_delta in delta_tool_calls:
                    index = tool_call_delta.get("index", len(tool_calls))
                    
                    if index >= len(tool_calls):
                        tool_calls.extend([
                            {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""}
                            }
                            for _ in range(index - len(tool_calls) + 1)
                        ])
                    
                    current = tool_calls[index]
                    
                    if "id" in tool_call_delta:
                        current["id"] = tool_call_delta["id"]
                    if "type" in tool_call_delta:
                        current["type"] = tool_call_delta["type"]
                    if "extra_content" in tool_call_delta:
                        current["extra_content"] = tool_call_delta["extra_content"]
                    
                    func_delta = tool_call_delta.get("function")
                    if func_delta:
                        current_func = current["function"]
                        if "name" in func_delta:
                            current_func["name"] += func_delta["name"]
                        if "arguments" in func_delta:
                            current_func["arguments"] += func_delta["arguments"]
        
        message = {"role": "assistant"}
        
        if reasoning_content:
            message["reasoning_content"] = reasoning_content
        if content:
            message["content"] = content
        if tool_calls:
            message["tool_calls"] = tool_calls
        
        if chunk and chunk.get("choices"):
            last_delta = chunk["choices"][0].get("delta", {})
            if "extra_content" in last_delta:
                message["extra_content"] = last_delta["extra_content"]
                
            if finish_reason := chunk["choices"][0].get("finish_reason"):
                pass
        
        result = {
            "choices": [{
                "index": 0,
                "message": message
            }]
        }
        
        if finish_reason:
            result["choices"][0]["finish_reason"] = finish_reason

        if "usage" in chunk:
            result["usage"] = chunk["usage"]
        
        return result
        
    
    async def client_post_stream(self):
        """模拟流式请求"""

        chunks = [
            { 'choices': [ { 'delta': { 'role': 'assistant',
                            'tool_calls': [ { 'extra_content': { 'google': { 'thought_signature': 'EvYCCvMCAXLI2nwmj0F1Gv60cKdmJbn/6W/P+SJq5wBDNsFChfFYN/CNSn0BGR9dYWIv+kcndzLNNnaPV+/yCzPzb2XR+ajKQxxC9HgbAIdVuHaj0MaHsnD/wS8MJCs9XkJYjNXCdtWrFhBJOZ88si/gmM0oh6BYQy6znnZWFMwIP2Fbnxk7tpO7rgMUlFIITDhNxBtThQ7rczCWFj9++coJ98sP/6ROgzdiA++VQvINNjcTemqU+LkMLttBndd2eEH6TIIwpxkqjqkZStwLnivD6fcU/ddCqg1iOezr4Xp30B90QRfg3qDA465LELusCTkUhXE8LhJhi89HCNQ+Z4kiO11v7KXiu5H3edUqAwnjjqWg1n9ez9zFdBru/ooQwB2NgCfcaUCVjpbw/aOW5i2eMPVmRitxYtabvsbX7LW5w8U9Jndg/Fd++2P5Wu6iuX8Hm+hAPkdlGj9yeNAePbP69qLBJ9W33t/5skHN7cAm5WyYJiA7R7Y='}},
                                              'function': { 'arguments': '{"location":"Beijing"}',
                                                            'name': 'get_weather'},
                                              'id': 'function-call-2345235027967754022',
                                              'type': 'function'}]},
                 'index': 0}],
  'created': 1769268035,
  'id': 'Q-N0ac2AK5OyvdIP9_rP-Ac',
  'model': 'gemini-3-flash-preview',
  'nonce': '320360292432325c',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'role': 'assistant',
                            'tool_calls': [ { 'function': { 'arguments': '{"location":"Wuhan"}',
                                                            'name': 'get_weather'},
                                              'id': 'function-call-2345235027967754215',
                                              'type': 'function'}]},
                 'index': 0}],
  'created': 1769268035,
  'id': 'Q-N0ac2AK5OyvdIP9_rP-Ac',
  'model': 'gemini-3-flash-preview',
  'nonce': '320360292432325c',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': {'role': 'assistant'},
                 'finish_reason': 'stop',
                 'index': 0}],
  'created': 1769268035,
  'id': 'Q-N0ac2AK5OyvdIP9_rP-Ac',
  'model': 'gemini-3-flash-preview',
  'nonce': '320360292432325c',
  'object': 'chat.completion.chunk'},
        ]
        
        for chunk in chunks:
            yield chunk

