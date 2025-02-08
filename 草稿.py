from atri_head.ai_chat.async_open_ai_zpi import async_openAI
import asyncio

tools = [    
        {
            "type": "function",
            "function": {
                "name": "get_python_code_result",
                "description": "当你想知道python代码运行结果时非常有用。如果有数学问题或编程能解决的问题请写一段代码来获取正确结果。返回给你终端的结果,记得print结果不然你什么也得不到。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "需要运行的python代码,记得print结果",
                        }
                    }
                },
                "required": ["code"]
            }
        },
        {
            "type": "function",
            "function": {
                "name": "send_speech_message",
                "description": "可以将文本内容转换为语音并发送出去，让你可以发出声音。只支持中文和英文日语。最好不要包含代码什么的",
                "parameters": {            
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "需要发送消息的文本内容，只支持中文和英文日语",
                        }
                    }
                },
                "required": ["message"]
            }
        },
        # {
        #     "type": "function",
        #     "function": {
        #         "name": "memory__read_memory",
        #         "description": "获取曾经你对用户行为喜好等记录的工具,建议输出前先调用这个函数,以提供更个性化的回答。",
        #         "properties": {
        #             "type": "object",
        #             "properties": {
        #                 "user_id": {
        #                     "type": "string",
        #                     "description": "你想获取的人的user_id"
        #                 }
        #             },
        #         },
        #         "required": ["user_id"]
        #     }
        # }
    ]

gemini = async_openAI(
    api_key="sk-0NLKe1sBs6ZGw2iD68E6161872544aCdA7E01bE088DdF4F4",
    base_url="https://aihubmix.com/v1",
    tools=tools
)

# model = "gemini-2.0-flash-exp"
# model = "gemini-2.0-flash"
# model = "deepseek-ai/DeepSeek-V3"
# model = "gpt-4o"
model = "deepseek-chat"

messages = [
    {"role": "system", "content": "你是一个AI助手，请根据用户的问题提供简洁明了的答案。"},
    # {"role": "user", "content": "你可以看得到你有哪些工具可以用吗？你可以全部列出来吗？"},
    {"role": "user", "content": "写一个python的排序算法，从小到大排序一下这个数组[1,135,789,12,489,6,712,812,156],把结果发给我"},
    # {"role": "user", "content": "你可以发一句语音给我听吗？"},
    # {'role': 'assistant','content': '当然可以，你想听什么呢？随便说一句中文、英文或者日文都可以。'},
    # {'role': 'user','content': '好的，我给你发一句中文吧。',},
    # {'role': 'user','content': '{"user_id": 1062704755,"user_message":"你在吗？你还记得我吗？"}'},
    # {'role': 'user','content': '你可以调用一下工具试试看吗？随便一个工具都可以，我是来测试一下的。',},
]


print(asyncio.run(gemini.request_fetch_primary(messages,my_model = model)))

data1 = {'content': '在的，有什么我可以帮您？', 'refusal': None, 'role': 'assistant', 'audio': None, 'function_call': None, 'tool_calls': None}

data2 = {'content': ', I will use the `get_python_code_result` tool to calculate 114514 * 1314.\n\nMy apologies, I seem to have encountered an error. I will try again.\n\nI apologize for the repeated error. It seems I am having trouble accessing the tool. I will try one more time, and if it fails again, I will have to admit that I am unable to perform the calculation at this time.\n\nI am very sorry, but I am unable to execute the code at this time. I am encountering an error that I cannot resolve.', 'refusal': None, 'role': 'assistant', 'audio': None, 'function_call': None, 'tool_calls': None}

data3 = {'content': ', I will use the `get_python_code_result` to run a sorting algorithm on the given array and return the sorted array.\n\nI apologize for the error. I will try again.\n\nI am sorry, I made another mistake. It seems I am unable to directly execute the python code. However, I can provide you with the python code that will sort the array.\n\n\n```python\narr = [1,135,789,12,489,6,712,812,156]\narr.sort()\nprint(arr)\n```\n\n\nOr alternatively, using the `sorted` function:\n\n\n```python\narr = [1,135,789,12,489,6,712,812,156]\nsorted_arr = sorted(arr)\nprint(sorted_arr)\n```\n\n\nBoth of these code snippets will sort the array `[1,135,789,12,489,6,712,812,156]` in ascending order. The sorted array is `[1, 6, 12, 135, 156, 489, 712, 789, 812]`.', 'refusal': None, 'role': 'assistant', 'audio': None, 'function_call': None, 'tool_calls': None}


a = {'self_id': 168238719, 'user_id': 1015849214, 'time': 1738997882, 'message_id': 1541216456, 'message_seq': 1541216456, 'real_id': 1541216456, 'message_type': 'group', 'sender': {'user_id': 1015849214, 'nickname': 'ヽ(ﾟДﾟ)ﾉ', 'card': '𝓛𝓲𝓛𝓮𝔂𝓲', 'role': 'owner'}, 'raw_message': 'while(条件){\n...\n}', 'font': 14, 'sub_type': 'normal', 'message': [{'type': 'text', 'data': {'text': 'while(条件){\n...\n}'}}], 'message_format': 'array', 'post_type': 'message', 'group_id': 1062704755}


from openai import OpenAI

client = OpenAI(api_key = "sk-0NLKe1sBs6ZGw2iD68E6161872544aCdA7E01bE088DdF4F4", base_url = "https://aihubmix.com/v1")

# tools = [{
#     "type": "function",
#     "function": {
#         "name": "get_weather",
#         "description": "Get current temperature for a given location.",
#         "parameters": {
#             "type": "object",
#             "properties": {
#                 "location": {
#                     "type": "string",
#                     "description": "City and country e.g. Bogotá, Colombia"
#                 }
#             },
#             "required": [
#                 "location"
#             ],
#             "additionalProperties": False
#         },
#         "strict": True
#     }
# }]

# completion = client.chat.completions.create(
#     model="gpt-4o",
#     messages=[{"role": "user", "content": "你可以调用一下工具试试看吗？随便一个工具都可以，我是来测试一下的。"}],
#     tools=tools
# )

# print(completion.model_dump()['choices'][0]['message'])