from ..Basics.qq_send_message import QQ_send_message
from .model_api.bigModel_api import async_bigModel_api
# from .model_api.async_open_ai_api import async_openAI
from ..Basics import Basics
import asyncio
import importlib.util
import httpx
import random
import os
import json
# from pprint import pp

class tool_calls:
    """
    工具调用类
    """

    def __init__(self):
        self.passing_message = QQ_send_message()
        self.basics = Basics()
        self.mcp_tool = self.basics.mcp_tool
        """掌管MCP的""" 
        self.tools_functions_dict = {
        }
        self.tools_functions_dict_qq = {
            'send_speech_message': self.send_speech_message,
            'send_image_message': self.send_image_message,
            'send_cloud_music': self.send_cloud_music,
            # 'send_text_message': self.send_text_message,
        }
        self.tools = TOOLS
        
        #tool
        self.mcp_service_queue = asyncio.Queue()
        self.mcp_service_task = asyncio.create_task(self.mcp_tool.mcp_service_selector())#mcp控制方法
        self.mcp_tool.mcp_service_queue.put_nowait({"type": "init"})#初始化所有MCP客户端
        self.load_additional_tools()
        
        self.basics.AI_supplier_manager.add_connection(
            name = "bigModel",
            connection_object = async_bigModel_api()
        )


    async def calls(self, tool_name, arguments_str, group_ID):
        """调用工具"""
        if tool_name in self.tools_functions_dict_qq:
            try:
                
                if arguments_str == "{}":   
                    return await self.tools_functions_dict_qq[tool_name]({"group_ID":group_ID})
                else: 
                    return await self.tools_functions_dict_qq[tool_name](**(json.loads(arguments_str)|{"group_ID":group_ID}))
                
            except TypeError as e:
                print(f"函数调用参数错误: {e}")
            except KeyError as e:
                print(f"工具函数未实现: {e}")
        elif func_tool := self.mcp_tool.get_func(tool_name):
            #MCP工具的调用
            return await func_tool.execute(**json.loads(arguments_str))
        else:
            raise Exception(f"Request function {tool_name} not found.")


    def load_additional_tools(self)->list:
        """加载额外工具"""
        print("加载模型tools...")
        
        self.get_files_in_folder()

        self.tools = self.tools + self.mcp_tool.get_func_desc_openai_style()
        print("加载模型tools完成!\n")
        return self.tools


    def get_files_in_folder(self):
        """获添加文件夹中的所有工具函数和工具json"""

        folder_path = "atri_head/ai_chat/tools/"
        default_module_name = "main"

        for name in os.listdir(folder_path):
            dir_path = os.path.join(folder_path, name)
            if os.path.isdir(dir_path):

                file_path = os.path.join(dir_path, "__init__.py")
                if not os.path.exists(file_path):
                    print(f"文件夹{dir_path}中没有__init__.py文件")
                    continue 

                # module_name = f"tools.{name}"

                spec = importlib.util.spec_from_file_location(name, file_path)
                
                if spec is None:
                    print(f"导入模块{file_path} 失败！")
                    continue

                module = importlib.util.module_from_spec(spec)

                if module is None:
                    print(f"获取模块{file_path}中的loader 失败！")
                    continue

                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    print(f"加载模块时发生错误：{e}")
                    continue

                func = getattr(module, default_module_name, None)
                if func is None:
                    print(f"获取模块{file_path}中的函数{default_module_name} 失败！")
                    continue
                
                tool_json = getattr(module, "tool_json", None)
                if tool_json is None:
                    print(f"获取模块{file_path}中的函数tool_json 失败！")
                    continue
                
                self.mcp_tool.add_func(
                    name = tool_json["name"],
                    func_args = {} if tool_json["properties"] is None else tool_json["properties"],
                    desc = tool_json["description"],
                    handler = func
                )

    def get_all_tools_json(self)->list:
        """获取默认的全部工具json"""
        return TOOLS + self.mcp_tool.get_func_desc_openai_style()


    def generate_integrity_tools_json(self, tool_json:dict):
        """生成一个工具的完整json"""
        
        properties:dict = tool_json.get("properties") or {}
        #允许properties没有，或值为None
        
        tool_json_integrity = {
            "type": "function",
            "function": {
                "name": tool_json["name"],
                "description": tool_json["description"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                }
            }
        }
        
        if properties:
            tool_json_integrity["function"]["required"] = list(properties.keys())
        
        return tool_json_integrity
     
    # async def send_text_message(self, message, group_ID):
    #     """发送文本消息"""
    #     await self.passing_message.send_group_message(group_ID,message)

    #     return {"send_text_message": f"已发送:{message}"}
    
    async def send_speech_message(self, text,group_ID, emotion="高兴", speed=0.9):
        """发送语音消息"""
        url = await self.basics.AI_interaction.get_tts_path(
            text,
            emotion,
            speed
        )
        await self.passing_message.send_group_audio(group_ID, url,default=True)

        return {"send_speech_message": f"已发送：{text}<NOTICE>需要再调用tool_calls_end工具代表工具调用结束</NOTICE>"}
    
    async def send_image_message(self, prompt, group_ID, width="1024", height="1024"):
        """生成发送图片消息"""
        model = "gptimage" #flux,kontext,turbo,gptimage
        Token = "56zs_9uGTfe19hUH"
        Seed = random.randint(1, 2_147_483_647)
        
        # url = await self.model.generate_image(prompt)
        #&enhance=true
        url = f"https://image.pollinations.ai/prompt/{prompt}?width={width}&height={height}&private=true&Seed={Seed}&Model={model}&Token={Token}"
    
        data = await self.passing_message.send_group_pictures(group_ID,url,local_Path_type=False,get_return=True)
        # print("图片发送成功")
        return {"send_image_message": {"status":f"{data}<NOTICE>需要再调用tool_calls_end工具代表工具调用结束</NOTICE>"}}
    
    async def send_cloud_music(self, name:str,group_ID:int|str):
        """分享网易云歌曲

        Args:
            name (str): 歌曲名称
            group_ID (int | str): 群号一般自动传入
        """
        async def search_music(keywords, limit=5)->list[dict]:
            """
            网易云音乐搜索接口，返回歌曲信息列表
            
            Args:
                :keywords 搜索关键词
                :limit 返回数量
                
            Returns:
                歌曲名和id
                [{'name': '冬の花', 'id': 1345485069},...]
            """
            url = 'https://music.163.com/api/cloudsearch/pc'
            data = {'s': keywords, 'type': 1, 'limit': limit}
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://music.163.com/'
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data, headers=headers)
            data = response.json()
            # print(data)
            return [{"name":v["name"],"id":v["id"]}  for v in data['result'].get('songs',[])]
        
        if music_lsit := await search_music(name):
            await self.basics.QQ_send_message.send_group_music(
                group_ID,
                "163",
                str(music_lsit[0]["id"])
            )
            
            return {"send_cloud_music":f"已发送:{music_lsit[0]["name"]}<NOTICE>需要再调用tool_calls_end工具代表工具调用结束</NOTICE>"}
        else:
            return {"send_cloud_music":"没有这首歌"}
    

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "send_speech_message",
            "description": "在需要你发语音或是让你说话的时候使用,将文本内容转换为语音消息并进行发送,要避免输入符号等不可读文本",
            "parameters": {            
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "需转换为语音的文本内容（支持中文/英文/日语）可以混合语言",
                    },
                    "emotion": {
                        "type": "string",
                        "description": "音频的情感,默认为高兴,支持的枚举值：高兴,机械,平静",
                    },
                    "speed": {
                        "type": "string",
                        "description": "语速，取值范围0.6~1.65,默认1",
                    }
                }
            },
            "required": ["text"]
        }
    },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "send_text_message",
    #         "description": "用来发送文本消息(不会结束工具调用,发完后一般调用工具tool_calls_end)，适用于需要连续发多条消息的多步场景。",
    #         "parameters": {            
    #             "type": "object",
    #             "properties": {
    #                 "message": {
    #                     "type": "string",
    #                     "description": "需要直接呈现给用户的文本内容",
    #                 }
    #             }
    #         },
    #         "required": ["message"]
    #     }
    # },
    {
        "type": "function",
        "function": {
            "name": "send_image_message",
            "description": "这是你的画板,图像生成工具，能够根据提示词自动生成对应的图片，并将生成的图片发送给用户。适用于需要你绘画的场景。",
            "parameters": {            
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "需要生成图片的prompt,只能是英文"
                    },
                    "width": {
                        "type": "string",
                        "description": "图像宽度，单位像素,默认1024"
                    },
                    "height": {
                        "type": "string",
                        "description": "图像高度，单位像素,默认1024"
                    },
                }
            },
            "required": ["prompt"]
        }
    },    
    {
        "type": "function",
        "function": {
            "name": "send_cloud_music",
            "description": "分享来源网易云的歌曲,有人让你唱歌可以调用这个工具",
            "parameters": {            
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "歌曲名称",
                    }
                }
            },
            "required": ["name"]
        }
    },
]