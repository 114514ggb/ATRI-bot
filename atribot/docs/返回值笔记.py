# from pprint import pp

# qq群消息返回值

Received_event={
'self_id': 168238719, # 接收者qq号 
'user_id': 2631018780, # 发送者qq号
'time': 1729865139, # 发消息时的时间戳
'message_id': 1941209958, # 消息id
'message_seq': 1941209958, # 消息序列号
'real_id': 1941209958,  # 消息真实id
'message_type': 'group', # 消息类型
'sender': {'user_id': 2631018780, # 发送者qq号
      'nickname': '除了摸鱼什么都做不到', # 发送者昵称
      'card': '',  # 发送者群名片
      'role': 'owner' # 发送者角色
    },
'raw_message': '?', # 消息内容原始cq码
'font': 14,  # 字体
'sub_type': 'normal', # 消息子类型
'message': [{
    'type': 'text', # 消息类型
    'data': {'text': '?'} # 消息内容
    }],
'message_format': 'array', #消息格式  
'post_type': 'message', # 事件类型
'group_id': 984466158 # 群号
}

图片消息= {
    #其他字段同上
    'message': [{
        'type': 'image',
        'data':{
            'file': 'file:D:\\图片\\Noeur喝咖啡.png'
        },
    }]
}

指令加图片= {
  "self_id": 168238719,
  "user_id": 2631018780,
  "time": 1735044726,
  "message_id": 1410911054,
  "message_seq": 1410911054,
  "real_id": 1410911054,
  "message_type": "group",
  "sender": {
    "user_id": 2631018780,
    "nickname": "除了摸鱼什么都做不到",
    "card": "",
    "role": "owner"
  },
  "raw_message": "[CQ:at,qq=168238719] /bot [CQ:image,file=000001464e61704361744f6e65426f747c4d736746696c657c327c3938343436363135387c373435313936303335373230333335393232337c373435313936303335373230333335393232327c4568544f3242494a66574872626a786d4f4a55615730306c795576424768697471674d675f776f6f2d767553704c6e4169674d794248427962325251674c326a41566f5162473878692d577251456b5a76523036346768313941.343363CA8F525A946D646AC0C4807CFE.png,sub_type=0,file_id=000001464e61704361744f6e65426f747c4d736746696c657c327c3938343436363135387c373435313936303335373230333335393232337c373435313936303335373230333335393232327c4568544f3242494a66574872626a786d4f4a55615730306c795576424768697471674d675f776f6f2d767553704c6e4169674d794248427962325251674c326a41566f5162473878692d577251456b5a76523036346768313941.343363CA8F525A946D646AC0C4807CFE.png,url=https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhTO2BIJfWHrbjxmOJUaW00lyUvBGhitqgMg_woo-vuSpLnAigMyBHByb2RQgL2jAVoQbG8xi-WrQEkZvR064gh19A&rkey=CAMSKLgthq-6lGU_XCHd1eAq-vdGAJnrpmRhqbytWceVs0BKZxIY7iadVqs,file_size=54573,file_unique=343363ca8f525a946d646ac0c4807cfe]",
  "font": 14,
  "sub_type": "normal",
  "message": [
    {
      "type": "at",
      "data": {
        "qq": "168238719"
      }
    },
    {
      "type": "text",
      "data": {
        "text": " /bot "
      }
    },
    {
    "type": "image",
    "data": {
        "summary": "",
        "file": "000001464e61704361744f6e65426f747c4d736746696c657c327c3938343436363135387c373435313936303335373230333335393232337c373435313936303335373230333335393232327c4568544f3242494a66574872626a786d4f4a55615730306c795576424768697471674d675f776f6f2d767553704c6e4169674d794248427962325251674c326a41566f5162473878692d577251456b5a76523036346768313941.343363CA8F525A946D646AC0C4807CFE.png",
        "sub_type": 0,
        "file_id": "000001464e61704361744f6e65426f747c4d736746696c657c327c3938343436363135387c373435313936303335373230333335393232337c373435313936303335373230333335393232327c4568544f3242494a66574872626a786d4f4a55615730306c795576424768697471674d675f776f6f2d767553704c6e4169674d794248427962325251674c326a41566f5162473878692d577251456b5a76523036346768313941.343363CA8F525A946D646AC0C4807CFE.png",
        "url": "https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhTO2BIJfWHrbjxmOJUaW00lyUvBGhitqgMg_woo-vuSpLnAigMyBHByb2RQgL2jAVoQbG8xi-WrQEkZvR064gh19A&rkey=CAMSKLgthq-6lGU_XCHd1eAq-vdGAJnrpmRhqbytWceVs0BKZxIY7iadVqs",
        "file_size": "54573",
        "file_unique": "343363ca8f525a946d646ac0c4807cfe"
    }
    }
    ],
    "message_format": "array",
    "post_type": "message",
    "group_id": 984466158
}

b站分享 ={
    'self_id': 168238719, 
    'user_id': 2631018780, 
    'time': 1732716735, 
    'message_id': 401713445, 
    'message_seq': 401713445, 
    'real_id': 401713445, 
    'message_type': 'group', 
    'sender': {
        'user_id': 2631018780, 
        'nickname': '除了摸鱼什么都做不到', 
        'card': '', 'role': 'owner'
        }, 
    'raw_message': '''[
        CQ:json,
        data={
            "ver":"1.0.0.19"&#44;
            "prompt":"&#91;QQ小程序&#93;点赞过500给兄弟们cos圣园未花"&#44;
            "config":{
                "type":"normal"&#44;
                "width":0&#44;
                "height":0&#44;
                "forward":1&#44;
                "autoSize":0&#44;
                "ctime":1732716722&#44;
                "token":"6341ca7a32d38ebf7cbf6a06a989f1a9"}&#44;
                "needShareCallBack":False&#44;
                "app":"com.tencent.miniapp_01"&#44;
                "view":"view_8C8E89B49BE609866298ADDFF2DBABA4"&#44;
                "meta":{
                    "detail_1":{
                        "appid":"1109937557"&#44;
                        "appType":0&#44;
                        "title":"哔哩哔哩"&#44;
                        "desc":"点赞过500给兄弟们cos圣园未花"&#44;
                        "icon":"https:\\/\\/open.gtimg.cn\\/open\\/app_icon\\/00\\/95\\/17\\/76\\/100951776_100_m.png?t=1732712948"&#44;
                        "preview":"pubminishare-30161.picsz.qpic.cn\\/3192ae3f-7806-4300-8d77-9c8ff62b937d"&#44;
                        "url":"m.q.qq.com\\/a\\/s\\/46cd378c3d94e2e3ad5abe57ecbf9291"&#44;
                        "scene":1036&#44;
                        "host":{
                            "uin":2631018780&#44;
                            "nick":"除了摸鱼什么都做不到"
                        }&#44;
                        "shareTemplateId":"8C8E89B49BE609866298ADDFF2DBABA4"&#44;
                        "shareTemplateData":{}&#44;
                        "qqdocurl":"https:\\/\\/b23.tv\\/SAkPU02?share_medium=android&amp;
                        share_source=qq&amp;
                        bbid=XU01C8F063EEC9EC918F03EEF83CA2CE7E695&amp;
                        ts=1732716714956"&#44;
                        "showLittleTail":""&#44;
                        "gamePoints":""&#44;
                        "gamePointsUrl":""&#44;
                        "shareOrigin":0
                    }
                }
            }
    ]''', 
    'font': 14, 
    'sub_type': 'normal', 
    'message': [{
        'type': 'json', 
        'data': {
            'data': {
                "ver":"1.0.0.19",
                "prompt":"[QQ小程序]点赞过500给兄弟们cos圣园未花",
                "config":{
                    "type":"normal",
                    "width":0,
                    "height":0,
                    "forward":1,
                    "autoSize":0,
                    "ctime":1732716722,
                    "token":"6341ca7a32d38ebf7cbf6a06a989f1a9"
                },
                "needShareCallBack":False,
                "app":"com.tencent.miniapp_01",
                "view":"view_8C8E89B49BE609866298ADDFF2DBABA4",
                "meta":{
                    "detail_1":{
                        "appid":"1109937557",#qq小程序给b站的id
                        "appType":0,#类型
                        "title":"哔哩哔哩",#小程序标题
                        "desc":"点赞过500给兄弟们cos圣园未花",#描述
                        "icon":"https:\\/\\/open.gtimg.cn\\/open\\/app_icon\\/00\\/95\\/17\\/76\\/100951776_100_m.png?t=1732712948", #应用图片
                        "preview":"pubminishare-30161.picsz.qpic.cn\\/3192ae3f-7806-4300-8d77-9c8ff62b937d",    #封面图片
                        "url":"m.q.qq.com\\/a\\/s\\/46cd378c3d94e2e3ad5abe57ecbf9291",#应该是小程序链接
                        "scene":1036,
                        "host":{  
                            "uin":2631018780,#发送人的qq号
                            "nick":"除了摸鱼什么都做不到"#发送人的网名
                        },
                        "shareTemplateId":"8C8E89B49BE609866298ADDFF2DBABA4",#分享模板id 加密过
                        "shareTemplateData":{},#分享模板数据
                        "qqdocurl":"https:\\/\\/b23.tv\\/SAkPU02?share_medium=android&share_source=qq&bbid=XU01C8F063EEC9EC918F03EEF83CA2CE7E695&ts=1732716714956",
                        "showLittleTail":"",#没看出来什么用
                        "gamePoints":"",
                        "gamePointsUrl":"",
                        "shareOrigin":0
                    }
                }
            }
        }
    }], 
    'message_format': 'array', 
    'post_type': 'message', 
    'group_id': 984466158
    }
"""
'post_type':'notice'事件是注意,会附带一个'notice_type'字段
'notice_type': 'group_recall' # 群撤回
'notice_type': 'notify' # 戳一戳
"""

语音文件={
    'self_id': 168238719,
    'user_id': 2631018780,
    'time': 1733809669, 
    'message_id': 1558358229, 
    'message_seq': 1558358229, 
    'real_id': 1558358229, 
    'message_type': 'group', 
    'sender': {
        'user_id': 2631018780, 
        'nickname': '除了摸鱼什么都做不到', 
        'card': '', 'role': 'owner'
    }, 
    'raw_message': '[CQ:record,file=000000924e61704361744f6e65426f747c4d736746696c657c327c3938343436363135387c373434363635353832363630323632333236307c373434363635353832363630323632333235397c.6025041d8b230c95db3ee8d382dd28e0.amr,path=D:\\Backup\\Documents\\Tencent Files\\168238719\\nt_qq\\nt_data\\Ptt\\2024-12\\Ori\\6025041d8b230c95db3ee8d382dd28e0.amr,url=file:///D:/Backup/Documents/Tencent%20Files/168238719/nt_qq/nt_data/Ptt/2024-12/Ori/6025041d8b230c95db3ee8d382dd28e0.amr,file_id=000000924e61704361744f6e65426f747c4d736746696c657c327c3938343436363135387c373434363635353832363630323632333236307c373434363635353832363630323632333235397c.6025041d8b230c95db3ee8d382dd28e0.amr,file_size=7294,file_unique=EhTVpdLu94kpNqDaBs4Q5PKLi0_wahj-OCD7CiiI3LOrwJyKAzIEcHJvZFCA9SRaEBM2VEs3JmI_IPn3e4ZuTeo]', 
    'font': 14, 
    'sub_type': 'normal', 
    'message': [{
        'type': 'record', 
        'data': {
            'file': '000000924e61704361744f6e65426f747c4d736746696c657c327c3938343436363135387c373434363635353832363630323632333236307c373434363635353832363630323632333235397c.6025041d8b230c95db3ee8d382dd28e0.amr', 
            'path': 'D:\\Backup\\Documents\\Tencent Files\\168238719\\nt_qq\\nt_data\\Ptt\\2024-12\\Ori\\6025041d8b230c95db3ee8d382dd28e0.amr', 
            'url': 'file:///D:/Backup/Documents/Tencent%20Files/168238719/nt_qq/nt_data/Ptt/2024-12/Ori/6025041d8b230c95db3ee8d382dd28e0.amr', 
            'file_id': '000000924e61704361744f6e65426f747c4d736746696c657c327c3938343436363135387c373434363635353832363630323632333236307c373434363635353832363630323632333235397c.6025041d8b230c95db3ee8d382dd28e0.amr', 
            'file_size': '7294', 
            'file_unique': 'EhTVpdLu94kpNqDaBs4Q5PKLi0_wahj-OCD7CiiI3LOrwJyKAzIEcHJvZFCA9SRaEBM2VEs3JmI_IPn3e4ZuTeo'
    }}], 
    'message_format': 'array', 
    'post_type': 'message', 
    'group_id': 984466158
}

引用的消息={
    'self_id': 168238719, 
    'user_id': 2631018780, 
    'time': 1733813542, 
    'message_id': 1997642738, 
    'message_seq': 1997642738, 
    'real_id': 1997642738, 
    'message_type': 'group',
    'sender': {
        'user_id': 2631018780, 
        'nickname': '除了摸鱼什么都做不到', 
        'card': '', 
        'role': 'owner'
    }, 
    'raw_message': '[CQ:reply,id=1381063063]啊啊啊啊', #id 是'message_id''message_seq''real_id'这里面的
    'font': 14, 
    'sub_type': 'normal', 
    'message': [
        {
            'type': 'reply', 
            'data': {
                'id': '1381063063'
            }
        }, 
        {
            'type': 'text', 
            'data': {
                'text': '啊啊啊啊'
            }
        }
    ], 
    'message_format': 'array', 
    'post_type': 'message', 
    'group_id': 984466158
}

{'model': 'ATRI', # 模型
 'created_at': '2024-10-25T16:11:26.3346754Z',  # 创建时间
 'message': {
    'role': 'assistant',  # 消息角色
    'content': '(ATRI兴奋地挥舞着尾巴，蓝色的眼睛闪闪发亮)\n\n喵呜！你好！我是ATRI，亚托利！很高兴认识你！(她伸出手，期待地望着你)你叫什么名字呢？ \n\n\n'
    }, 
    'done_reason': 'stop', # 结束原因
    'done': True, # 是否结束
    'total_duration': 25857024200, # 总耗时
    'load_duration': 14719482300, # 加载耗时
    'prompt_eval_count': 920, # 提示评估次数
    'prompt_eval_duration': 2078233000, # 提示评估耗时
    'eval_count': 55, # 评估次数
    'eval_duration': 9053667000 # 评估耗时
    }


qwen = {
  "id": "chatcmpl-70d0c77f-3d17-9062-865e-742421d7766b",
  "choices": [
    {
      "finish_reason": "stop",
      "index": 0,
      "logprobs": None,
      "message": {
        "content": "消息内容",
        "refusal": None,
        "role": "assistant",
        "audio": None,
        "function_call": None,
        "tool_calls": None
      }
    }
  ],
  "created": 1734764423,
  "model": "qwen-plus",
  "object": "chat.completion",
  "service_tier": None,
  "system_fingerprint": None,
  "usage": {
    "completion_tokens": 43,
    "prompt_tokens": 310,
    "total_tokens": 353,
    "completion_tokens_details": None,
    "prompt_tokens_details": None
  }
}

AI调参数 = {
  "id": "chatcmpl-ba6f4628-ae70-9ffb-b305-3c597e1e2de9",
  "choices": [
    {
      "finish_reason": "tool_calls",
      "index": 0,
      "logprobs": None,
      "message": {
        "content": "",
        "refusal": None,
        "role": "assistant",
        "audio": None,
        "function_call": None,
        "tool_calls": [
          {
            "id": "call_319384957f3f44ef9da9d4",
            "function": {
              "arguments": "{\"code\": \"import datetime\\nnow = datetime.datetime.now()\\nprint(now.strftime('%Y-%m-%d %H:%M:%S'))\"}",
              "name": "get_python_code_result"
            },
            "type": "function",
            "index": 0
          }
        ]
      }
    }
  ],
  "created": 1734777720,
  "model": "qwen-plus",
  "object": "chat.completion",
  "service_tier": None,
  "system_fingerprint": None,
  "usage": {
    "completion_tokens": 44,
    "prompt_tokens": 365,
    "total_tokens": 409,
    "completion_tokens_details": None,
    "prompt_tokens_details": None
  }
}


群求加入群 = {
    'time': 1742714781, 
    'self_id': 168238719, 
    'post_type': 'request', 
    'group_id': 1038698883, 
    'user_id': 3930909243, 
    'request_type': 'group', 
    'comment': '加入时回复的内容', 
    'flag': '1742714780404951', #唯一标识符同意或拒绝时使用
    'sub_type': 'add' #请求类型，add表示请求加入群聊，invite表示邀请入群,可能退群还有一个
}

批准入群= {
    'time': 1742722578, 
    'self_id': 168238719, 
    'post_type': 'notice', 
    'group_id': 1038698883, 
    'user_id': 3930909243, 
    'notice_type': 'group_increase', 
    'operator_id': 2631018780, 
    'sub_type': 'approve'
    }

踢出群={
    'time': 1742723427, 
    'self_id': 168238719, 
    'post_type': 'notice', 
    'group_id': 1038698883, 
    'user_id': 3930909243, 
    'notice_type': 'group_decrease', 
    'sub_type': 'kick', #'leave'表示主动退群，'kick'表示被踢出群聊
    'operator_id': 2631018780 #操作者id，自己主动退出的话就为0
    }


{'error': {'message': 'invalid image input', 'type': 'invalid_request_error', 'param': None, 'code': None}}


接收到的消息_质谱={
  "model": "glm-4v-flash",
  "created": 1736176617,
  "choices": [
    {
      "index": 0,
      "finish_reason": "stop",
      "message": {
        "content": "这是一个三维渲染的表情符号，通常用来表示思考或疑惑的状态。\n\n表情符号是黄色的，有一个向下的眉毛和一条直线嘴巴，给人一种沉思或不确定的感觉。它的左手抬起，扶着下巴，好像在深入思考某个问题。背景是白色的。",
        "role": "assistant",
        "tool_calls": None
      }
    }
  ],
  "request_id": "20250106231655a36e9aa9600f4e81",
  "id": "20250106231655a36e9aa9600f4e81",
  "usage": {
    "prompt_tokens": 1665,
    "completion_tokens": 54,
    "total_tokens": 1719
  }
}

#请求参数
Tavily_aip = { 
    "query": "who is Leo Messi?",  #需要执行的搜索关键词
    "topic": "general", #搜索类别general（常规）、news（新闻）
    "search_depth": "basic", #basic（基础搜索）、advanced（高级搜索）
    "max_results": 1, #返回的搜索结果最大数量0 ≤ x ≤ 20
    "time_range": None, #过滤结果的日期范围（从当前时间往前推）day、week、month、year（或缩写 d、w、m、y）
    "days": 3, #仅当 topic=news 时有效，指定从当前日期往前推的天数
    "include_answer": True, #是否包含由LLM生成的简短答案。basic 或 true 返回简要答案，advanced 返回更详细的答案。
    "include_raw_content": False, #是否包含搜索结果的原始HTML内容（已清洗和解析）
    "include_images": False, #是否同时执行图片搜索并包含结果
    "include_image_descriptions": False, #当 include_images=true 时，是否为每张图片生成描述文本
    "include_domains": [],#指定要包含的域名列表（仅搜索这些域名的结果)
    "exclude_domains": [] #指定要排除的域名列表（不搜索这些域名的结果）
}

Tavily_aip_Response = {
  "query": "Who is Leo Messi?", #实际执行的搜索关键词
  "answer": "Lionel Messi, born in 1987, is an Argentine footballer widely regarded as one of the greatest players of his generation. He spent the majority of his career playing for FC Barcelona, where he won numerous domestic league titles and UEFA Champions League titles. Messi is known for his exceptional dribbling skills, vision, and goal-scoring ability. He has won multiple FIFA Ballon d'Or awards, numerous La Liga titles with Barcelona, and holds the record for most goals scored in a calendar year. In 2014, he led Argentina to the World Cup final, and in 2015, he helped Barcelona capture another treble. Despite turning 36 in June, Messi remains highly influential in the sport.",
  #返回的LLM生成答案
  "images": [],#图片搜索结果列表。若 include_image_descriptions=true，每项包含 url 和 description。
  "results": [
    {
      "title": "Lionel Messi Facts | Britannica",
      "url": "https://www.britannica.com/facts/Lionel-Messi",
      "content": "Lionel Messi, an Argentine footballer, is widely regarded as one of the greatest football players of his generation. Born in 1987, Messi spent the majority of his career playing for Barcelona, where he won numerous domestic league titles and UEFA Champions League titles. Messi is known for his exceptional dribbling skills, vision, and goal",
      "score": 0.81025416,
      "raw_content": None
    }
  ],#按相关性排序的常规搜索结果列表
  "response_time": "1.67"#API请求耗时（单位：秒）
}



{'self_id': 168238719,
 'user_id': 2631018780,
 'time': 1746962048,
 'message_id': 1681552818,
 'message_seq': 1681552818,
 'real_id': 1681552818,
 'real_seq': '17547',
 'message_type': 'group',
 'sender': {'user_id': 2631018780,
            'nickname': '除了摸鱼什么都做不到',
            'card': '',
            'role': 'owner'},
 'raw_message': '[CQ:face,id=311,raw=&#91;object Object&#93;,chainCount=0]',
 'font': 14,
 'sub_type': 'normal',
 'message': [{'type': 'face',
              'data': {'id': '311',
                       'raw': {'faceIndex': 311,
                               'faceText': '[打call]',
                               'faceType': 3,
                               'packId': '1',
                               'stickerId': '1',
                               'sourceType': 1,
                               'stickerType': 1,
                               'resultId': '',
                               'surpriseId': '',
                               'randomType': 1,
                               'imageType': None,
                               'pokeType': None,
                               'spokeSummary': None,
                               'doubleHit': None,
                               'vaspokeId': None,
                               'vaspokeName': None,
                               'vaspokeMinver': None,
                               'pokeStrength': None,
                               'msgType': None,
                               'faceBubbleCount': None,
                               'oldVersionStr': None,
                               'pokeFlag': None,
                               'chainCount': 0},
                       'resultId': '',
                       'chainCount': 0}}],
 'message_format': 'array',
 'post_type': 'message',
 'group_id': 984466158}

data_music = {'self_id': 168238719,
 'user_id': 2631018780,
 'time': 1747056163,
 'message_id': 608767955,
 'message_seq': 608767955,
 'real_id': 608767955,
 'real_seq': '17564',
 'message_type': 'group',
 'sender': {'user_id': 2631018780,
            'nickname': '除了摸鱼什么都做不到',
            'card': '',
            'role': 'owner'},
 'raw_message': '[CQ:json,data={"app":"com.tencent.music.lua"&#44;"bizsrc":"qqconnect.sdkshare_music"&#44;"config":{"ctime":1747056163&#44;"forward":1&#44;"token":"497b267d3cd845a1e6efcf3113a0d71b"&#44;"type":"normal"}&#44;"extra":{"app_type":1&#44;"appid":100495085&#44;"msg_seq":7503549085075699365&#44;"uin":2631018780}&#44;"meta":{"music":{"app_type":1&#44;"appid":100495085&#44;"ctime":1747056163&#44;"desc":"ChiliChill/洛天依Official"&#44;"jumpUrl":"https://y.music.163.com/m/song?id=1439814454&amp;uct2=bQ4dedfQ%2BrlZBB%2BSvOs2CA%3D%3D&amp;fx-wechatnew=t1&amp;fx-wxqd=c&amp;fx-wordtest=&amp;fx-listentest=t3&amp;H5_DownloadVIPGift=&amp;playerUIModeId=76001&amp;PlayerStyles_SynchronousSharing=t3&amp;dlt=0846&amp;app_version=9.2.50"&#44;"musicUrl":"http://music.163.com/song/media/outer/url?id=1439814454&amp;userid=4875911958&amp;sc=wm&amp;tn="&#44;"preview":"https://p1.music.126.net/JyF6_2QvPlLSuXSgYDwi0Q==/109951164896130416.jpg?imageView=1&amp;thumbnail=1260z2680&amp;type=webp&amp;quality=80"&#44;"tag":"网易云音乐"&#44;"tagIcon":"https://i.gtimg.cn/open/app_icon/00/49/50/85/100495085_100_m.png"&#44;"title":"我的悲伤是水做的"&#44;"uin":2631018780}}&#44;"prompt":"&#91;分享&#93;我的悲伤是水做的"&#44;"ver":"0.0.0.1"&#44;"view":"music"}]',
 'font': 14,
 'sub_type': 'normal',
 'message': [{'type': 'json',
              'data': {'data': '{"app":"com.tencent.music.lua","bizsrc":"qqconnect.sdkshare_music","config":{"ctime":1747056163,"forward":1,"token":"497b267d3cd845a1e6efcf3113a0d71b","type":"normal"},"extra":{"app_type":1,"appid":100495085,"msg_seq":7503549085075699365,"uin":2631018780},"meta":{"music":{"app_type":1,"appid":100495085,"ctime":1747056163,"desc":"ChiliChill/洛天依Official","jumpUrl":"https://y.music.163.com/m/song?id=1439814454&uct2=bQ4dedfQ%2BrlZBB%2BSvOs2CA%3D%3D&fx-wechatnew=t1&fx-wxqd=c&fx-wordtest=&fx-listentest=t3&H5_DownloadVIPGift=&playerUIModeId=76001&PlayerStyles_SynchronousSharing=t3&dlt=0846&app_version=9.2.50","musicUrl":"http://music.163.com/song/media/outer/url?id=1439814454&userid=4875911958&sc=wm&tn=","preview":"https://p1.music.126.net/JyF6_2QvPlLSuXSgYDwi0Q==/109951164896130416.jpg?imageView=1&thumbnail=1260z2680&type=webp&quality=80","tag":"网易云音乐","tagIcon":"https://i.gtimg.cn/open/app_icon/00/49/50/85/100495085_100_m.png","title":"我的悲伤是水做的","uin":2631018780}},"prompt":"[分享]我的悲伤是水做 的","ver":"0.0.0.1","view":"music"}'
                       }}],
 'message_format': 'array',
 'post_type': 'message',
 'group_id': 984466158}


{'self_id': 168238719,
 'user_id': 2631018780,
 'time': 1747065345,
 'message_id': 1599966906,
 'message_seq': 1599966906,
 'real_id': 1599966906,
 'real_seq': '30',
 'message_type': 'private',
 'sender': {'user_id': 2631018780, 'nickname': '除了摸鱼什么都做不到', 'card': ''},
 'raw_message': '1',
 'font': 14,
 'sub_type': 'friend',
 'message': [{'type': 'text', 'data': {'text': '1'}}],
 'message_format': 'array',
 'post_type': 'message',
 'target_id': 2631018780}


{'self_id': 168238719,
 'user_id': 2631018780,
 'time': 1747065509,
 'message_id': 739949050,
 'message_seq': 739949050,
 'real_id': 739949050,
 'real_seq': '17566',
 'message_type': 'group',
 'sender': {'user_id': 2631018780,
            'nickname': '除了摸鱼什么都做不到',
            'card': '',
            'role': 'owner'},
 'raw_message': 'aaa',
 'font': 14,
 'sub_type': 'normal',
 'message': [{'type': 'text', 'data': {'text': 'aaa'}}],
 'message_format': 'array',
 'post_type': 'message',
 'group_id': 984466158}


{'self_id': 168238719,
 'user_id': 2631018780,
 'time': 1747498237,
 'message_id': 2022112003,
 'message_seq': 2022112003,
 'real_id': 2022112003,
 'real_seq': '17671',
 'message_type': 'group',
 'sender': {'user_id': 2631018780,
            'nickname': '除了摸鱼什么都做不到',
            'card': '',
            'role': 'owner'},
 'raw_message': '[CQ:forward,id=7505447777902448728,content=&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;]',
 'font': 14,
 'sub_type': 'normal',
 'message': [{'type': 'forward',
              'data': {'id': '7505447777902448728',
                       'content': [{'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496006,
                                    'message_id': 219652570,
                                    'message_seq': 219652570,
                                    'real_id': 219652570,
                                    'real_seq': '614462',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': '沐浴晨煦',
                                               'card': ''},
                                    'raw_message': '[CQ:image,file=B443DC56BAFF2ED03BED8850FC333778.png,sub_type=0,url=https://multimedia.nt.qq.com.cn/download?appid=1407&amp;fileid=EhRxSBl93YeECeGQSi9KVUrsfq4QAxizl0Ig_wooxIqMnfKqjQMyBHByb2RQgL2jAVoQjFFGbp7TE-RefDapLe45kXoClBc&amp;rkey=CAESMJZSSJLfjR_PjtEECx-kZN6JCeGDYSevzHMan6iuIRt2KRxLY6IsoDeasIm99ippDQ,file_size=1084339]',      
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'image',
                                                 'data': {'summary': '',
                                                          'file': 'B443DC56BAFF2ED03BED8850FC333778.png',
                                                          'sub_type': 0,
                                                          'url': 'https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhRxSBl93YeECeGQSi9KVUrsfq4QAxizl0Ig_wooxIqMnfKqjQMyBHByb2RQgL2jAVoQjFFGbp7TE-RefDapLe45kXoClBc&rkey=CAESMJZSSJLfjR_PjtEECx-kZN6JCeGDYSevzHMan6iuIRt2KRxLY6IsoDeasIm99ippDQ',
                                                          'file_size': '1084339'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496008,
                                    'message_id': 356779939,
                                    'message_seq': 356779939,
                                    'real_id': 356779939,
                                    'real_seq': '614463',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': '沐浴晨煦',
                                               'card': ''},
                                    'raw_message': 'AI写的响应式',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': 'AI写的响应式'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496011,
                                    'message_id': 1679928360,
                                    'message_seq': 1679928360,
                                    'real_id': 1679928360,
                                    'real_seq': '614464',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': '沐浴晨煦',
                                               'card': ''},
                                    'raw_message': '我的天',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '我的天'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 168238719,
                                    'time': 1747496012,
                                    'message_id': 817905172,
                                    'message_seq': 817905172,
                                    'real_id': 817905172,
                                    'real_seq': '614465',
                                    'message_type': 'group',
                                    'sender': {'user_id': 168238719,
                                               'nickname': 'ATRI',
                                               'card': ''},
                                    'raw_message': '我的天!',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '我的天!'}}],
                                    'message_format': 'array',
                                    'post_type': 'message_sent',
                                    'message_sent_type': 'self',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496017,
                                    'message_id': 1435027738,
                                    'message_seq': 1435027738,
                                    'real_id': 1435027738,
                                    'real_seq': '614466',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': '沐浴晨煦',
                                               'card': ''},
                                    'raw_message': '比多少人写的要好',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '比多少人写的要好'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496034,
                                    'message_id': 2093161635,
                                    'message_seq': 2093161635,
                                    'real_id': 2093161635,
                                    'real_seq': '614467',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': '沐浴晨煦',
                                               'card': ''},
                                    'raw_message': '[CQ:image,file=96E3B4FCBE739EE4BFD37C6238CD588C.png,sub_type=0,url=https://multimedia.nt.qq.com.cn/download?appid=1407&amp;fileid=EhSQVIflrX1JBE8nMEkijmQjX51khBi61wog_woojZaMnfKqjQMyBHByb2RQgL2jAVoQvm-8cGLrCgXtjrDno5r2enoC2ik&amp;rkey=CAESMJZSSJLfjR_PjtEECx-kZN6JCeGDYSevzHMan6iuIRt2KRxLY6IsoDeasIm99ippDQ,file_size=175034]',       
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'image',
                                                 'data': {'summary': '',
                                                          'file': '96E3B4FCBE739EE4BFD37C6238CD588C.png',
                                                          'sub_type': 0,
                                                          'url': 'https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhSQVIflrX1JBE8nMEkijmQjX51khBi61wog_woojZaMnfKqjQMyBHByb2RQgL2jAVoQvm-8cGLrCgXtjrDno5r2enoC2ik&rkey=CAESMJZSSJLfjR_PjtEECx-kZN6JCeGDYSevzHMan6iuIRt2KRxLY6IsoDeasIm99ippDQ',
                                                          'file_size': '175034'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496036,
                                    'message_id': 600974802,
                                    'message_seq': 600974802,
                                    'real_id': 600974802,
                                    'real_seq': '614468',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': '沐浴晨煦',
                                               'card': ''},
                                    'raw_message': 'dashboard',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': 'dashboard'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496077,
                                    'message_id': 1763333962,
                                    'message_seq': 1763333962,
                                    'real_id': 1763333962,
                                    'real_seq': '614469',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': '沐浴晨煦',
                                               'card': ''},
                                    'raw_message': '这单AI占了80%',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '这单AI占了80%'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496083,
                                    'message_id': 2052006763,
                                    'message_seq': 2052006763,
                                    'real_id': 2052006763,
                                    'real_seq': '614470',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': '沐浴晨煦',
                                               'card': ''},
                                    'raw_message': '能收6k',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '能收6k'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496085,
                                    'message_id': 1636611,
                                    'message_seq': 1636611,
                                    'real_id': 1636611,
                                    'real_seq': '614471',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': '沐浴晨煦',
                                               'card': ''},
                                    'raw_message': '爽',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '爽'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496200,
                                    'message_id': 1789835577,
                                    'message_seq': 1789835577,
                                    'real_id': 1789835577,
                                    'real_seq': '614472',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': 'Maple-Kaede',
                                               'card': ''},
                                    'raw_message': '草',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '草'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 168238719,
                                    'time': 1747496201,
                                    'message_id': 355665788,
                                    'message_seq': 355665788,
                                    'real_id': 355665788,
                                    'real_seq': '614473',
                                    'message_type': 'group',
                                    'sender': {'user_id': 168238719,
                                               'nickname': 'ATRI',
                                               'card': ''},
                                    'raw_message': '草',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '草'}}],
                                    'message_format': 'array',
                                    'post_type': 'message_sent',
                                    'message_sent_type': 'self',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496212,
                                    'message_id': 779612996,
                                    'message_seq': 779612996,
                                    'real_id': 779612996,
                                    'real_seq': '614474',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': 'Maple-Kaede',
                                               'card': ''},
                                    'raw_message': '什么ai（',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '什么ai（'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496238,
                                    'message_id': 2119198234,
                                    'message_seq': 2119198234,
                                    'real_id': 2119198234,
                                    'real_seq': '614475',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': '沐浴晨煦',
                                               'card': ''},
                                    'raw_message': '豆包',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '豆包'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 2631018780,
                                    'time': 1747496292,
                                    'message_id': 662024412,
                                    'message_seq': 662024412,
                                    'real_id': 662024412,
                                    'real_seq': '614476',
                                    'message_type': 'group',
                                    'sender': {'user_id': 2631018780,
                                               'nickname': '除了摸鱼什么都做不到',
                                               'card': ''},
                                    'raw_message': '豆包编程这么好用吗',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '豆包编程这么好用吗'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 2631018780,
                                    'time': 1747496297,
                                    'message_id': 69699820,
                                    'message_seq': 69699820,
                                    'real_id': 69699820,
                                    'real_seq': '614477',
                                    'message_type': 'group',
                                    'sender': {'user_id': 2631018780,
                                               'nickname': '除了摸鱼什么都做不到',
                                               'card': ''},
                                    'raw_message': '下次试试',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '下次试试'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496389,
                                    'message_id': 1448515941,
                                    'message_seq': 1448515941,
                                    'real_id': 1448515941,
                                    'real_seq': '614478',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': 'Maple-Kaede',
                                               'card': ''},
                                    'raw_message': '效果这么好吗',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '效果这么好吗'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496424,
                                    'message_id': 699097483,
                                    'message_seq': 699097483,
                                    'real_id': 699097483,
                                    'real_seq': '614479',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': 'Limitee',
                                               'card': ''},
                                    'raw_message': '[CQ:reply,id=1213784349]一般',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'reply',
                                                 'data': {'id': '1213784349'}},
                                                {'type': 'text',
                                                 'data': {'text': '一般'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1747496430,
                                    'message_id': 1773992280,
                                    'message_seq': 1773992280,
                                    'real_id': 1773992280,
                                    'real_seq': '614480',
                                    'message_type': 'group',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': 'Limitee',
                                               'card': ''},
                                    'raw_message': '早就有实现的',
                                    'font': 14,
                                    'sub_type': 'normal',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '早就有实现 的'}}],
                                    'message_format': 'array',
                                    'post_type': 'message',
                                    'group_id': 284840486}]}}],
 'message_format': 'array',
 'post_type': 'message',
 'group_id': 984466158}



{
  "status": "ok",
  "retcode": 0,
  "data": {
    "uid": "u_XZ-4duRgDwzUuVtzM9VFmA",
    "uin": "2631018780",
    "nick": "除了摸鱼什么都做不到",
    "remark": "",
    "constellation": 1,
    "shengXiao": 10,
    "kBloodType": 5,
    "homeTown": "250-0-230",
    "makeFriendCareer": 1,
    "pos": "87",
    "college": "",
    "country": "中国",
    "province": "北京",
    "city": "丰台",
    "postCode": "24567",
    "address": "www.",
    "regTime": 1483233852,
    "interest": "",
    "labels": [],
    "qqLevel": 56,
    "qid": "printf1145",
    "longNick": "野蛮人之间人吃人，文明人之间人骗人。",
    "birthday_year": 2005,
    "birthday_month": 2,
    "birthday_day": 14,
    "age": 20,
    "sex": "male",
    "eMail": "1145141980qwq@gmail.com",
    "phoneNum": "-",
    "categoryId": 0,
    "richTime": 1749628512,
    "richBuffer": {
      "0": 3,
      "1": 54,
      "2": 233,
      "3": 135,
      "4": 142,
      "5": 232,
      "6": 155,
      "7": 174,
      "8": 228,
      "9": 186,
      "10": 186,
      "11": 228,
      "12": 185,
      "13": 139,
      "14": 233,
      "15": 151,
      "16": 180,
      "17": 228,
      "18": 186,
      "19": 186,
      "20": 229,
      "21": 144,
      "22": 131,
      "23": 228,
      "24": 186,
      "25": 186,
      "26": 239,
      "27": 188,
      "28": 140,
      "29": 230,
      "30": 150,
      "31": 135,
      "32": 230,
      "33": 152,
      "34": 142,
      "35": 228,
      "36": 186,
      "37": 186,
      "38": 228,
      "39": 185,
      "40": 139,
      "41": 233,
      "42": 151,
      "43": 180,
      "44": 228,
      "45": 186,
      "46": 186,
      "47": 233,
      "48": 170,
      "49": 151,
      "50": 228,
      "51": 186,
      "52": 186,
      "53": 227,
      "54": 128,
      "55": 130,
      "56": 144,
      "57": 28,
      "58": 50,
      "59": 54,
      "60": 51,
      "61": 49,
      "62": 48,
      "63": 49,
      "64": 56,
      "65": 55,
      "66": 56,
      "67": 48,
      "68": 54,
      "69": 48,
      "70": 51,
      "71": 54,
      "72": 52,
      "73": 57,
      "74": 54,
      "75": 56,
      "76": 98,
      "77": 48,
      "78": 98,
      "79": 97,
      "80": 48,
      "81": 54,
      "82": 48,
      "83": 48,
      "84": 54,
      "85": 48
    },
    "topTime": "0",
    "isBlock": False,
    "isMsgDisturb": False,
    "isSpecialCareOpen": False,
    "isSpecialCareZone": False,
    "ringId": "",
    "isBlocked": False,
    "recommendImgFlag": 1,
    "disableEmojiShortCuts": 0,
    "qidianMasterFlag": 0,
    "qidianCrewFlag": 0,
    "qidianCrewFlag2": 0,
    "isHideQQLevel": 0,
    "isHidePrivilegeIcon": 0,
    "status": 20,
    "extStatus": 0,
    "batteryStatus": 0,
    "termType": 0,
    "netType": 0,
    "iconType": 0,
    "customStatus": None,
    "setTime": "0",
    "specialFlag": 0,
    "abiFlag": 0,
    "eNetworkType": 0,
    "showName": "",
    "termDesc": "",
    "musicInfo": {
      "buf": {}
    },
    "extOnlineBusinessInfo": {
      "buf": {},
      "customStatus": None,
      "videoBizInfo": {
        "cid": "",
        "tvUrl": "",
        "synchType": ""
      },
      "videoInfo": {
        "name": ""
      }
    },
    "extBuffer": {
      "buf": {}
    },
    "user_id": 2631018780,
    "nickname": "除了摸鱼什么都做不到",
    "long_nick": "野蛮人之间人吃人，文明人之间人骗人。",
    "reg_time": 1483233852,
    "is_vip": False,
    "is_years_vip": False,
    "vip_level": 0,
    "login_days": 0
  },
  "message": "",
  "wording": "",
  "echo": ""
}

发消息返回值 = {
  "status": "ok",
  "retcode": 0,
  "data": {
    "message_id": 1752703775
  },
  "message": "",
  "wording": "",
  "echo": ""
}

退出群聊={
  'time': 1753193447, 
  'self_id': 168238719, 
  'post_type': 'notice', 
  'group_id': 1054558635, 
  'user_id': 2083303934, 
  'notice_type': 'group_decrease', 
  'sub_type': 'leave', 
  'operator_id': 0
  }


bot_消息 ={'self_id': 3930909243,
 'user_id': 3930909243,
 'time': 1761822407,
 'message_id': 1834007169,
 'message_seq': 1834007169,
 'real_id': 1834007169,
 'real_seq': '27107',
 'message_type': 'group',
 'sender': {'user_id': 3930909243,
            'nickname': 'atri-bot',
            'card': '莉基哈',
            'role': 'member'},
 'raw_message': '你又说废物！',
 'font': 14,
 'sub_type': 'normal',
 'message': [{'type': 'text', 'data': {'text': '你又说废物！'}}],
 'message_format': 'array',
 'post_type': 'message_sent',
 'message_sent_type': 'self',
 'group_id': 2169027872,
 'group_name': '一群泡茶的屑',
 'target_id': 2169027872}


{'self_id': 3930909243,
 'user_id': 168238719,
 'time': 1763916422,
 'message_id': 357172972,
 'message_seq': 357172972,
 'real_id': 357172972,
 'real_seq': '21052',
 'message_type': 'group',
 'sender': {'user_id': 168238719,
            'nickname': 'ATRI-bot',
            'card': '',
            'role': 'admin'},
 'raw_message': '主人是在找ATRI吗？',
 'font': 14,
 'sub_type': 'normal',
 'message': [{'type': 'text', 'data': {'text': '主人是在找ATRI吗？'}}],
 'message_format': 'array',
 'post_type': 'message',
 'group_id': 984466158,
 'group_name': '个人の群'}


{'self_id': 168238719,
 'user_id': 2631018780,
 'time': 1753859144,
 'message_id': 1248953984,
 'message_seq': 1248953984,
 'real_id': 1248953984,
 'real_seq': '19163',
 'message_type': 'group',
 'sender': {'user_id': 2631018780,
            'nickname': '除了摸鱼什么都做不到',
            'card': '',
            'role': 'owner'},
 'raw_message': '[CQ:reply,id=2129573382]回复1\n'
                '\n'
                '[CQ:image,file=9809170582BACD5ABA931EE773764769.png,sub_type=0,url=https://multimedia.nt.qq.com.cn/download?appid=1407&amp;fileid=EhQExAMTODKWQpETrxDr-7xEfnMb3hjSiwUg_woopYrmuYLkjgMyBHByb2RQgL2jAVoQuAzImxK4FkAYIWlPchuTU3oCxF8&amp;rkey=CAQSMAzKd0AktjAfxaVvagQj4o2iKqlZffe8rt3gH3qDtUmRDllUmc619HPtz9mYtLzE4Q,file_size=83410]回复2\n'
                '[CQ:image,file=9809170582BACD5ABA931EE773764769.png,sub_type=0,url=https://multimedia.nt.qq.com.cn/download?appid=1407&amp;fileid=EhQExAMTODKWQpETrxDr-7xEfnMb3hjSiwUg_woou7ySuoLkjgMyBHByb2RQgL2jAVoQfl7NOLvQ1R1z04CVj6sFGnoCThY&amp;rkey=CAQSMAzKd0AktjAfxaVvagQj4o2iKqlZffe8rt3gH3qDtUmRDllUmc619HPtz9mYtLzE4Q,file_size=83410]回复3',
 'font': 14,
 'sub_type': 'normal',
 'message': [{'type': 'reply', 'data': {'id': '2129573382'}},
             {'type': 'text', 'data': {'text': '回复1\n\n'}},
             {'type': 'image',
              'data': {'summary': '',
                       'file': '9809170582BACD5ABA931EE773764769.png',
                       'sub_type': 0,
                       'url': 'https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhQExAMTODKWQpETrxDr-7xEfnMb3hjSiwUg_woopYrmuYLkjgMyBHByb2RQgL2jAVoQuAzImxK4FkAYIWlPchuTU3oCxF8&rkey=CAQSMAzKd0AktjAfxaVvagQj4o2iKqlZffe8rt3gH3qDtUmRDllUmc619HPtz9mYtLzE4Q',
                       'file_size': '83410'}},
             {'type': 'text', 'data': {'text': '回复2\n'}},
             {'type': 'image',
              'data': {'summary': '',
                       'file': '9809170582BACD5ABA931EE773764769.png',
                       'sub_type': 0,
                       'url': 'https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhQExAMTODKWQpETrxDr-7xEfnMb3hjSiwUg_woou7ySuoLkjgMyBHByb2RQgL2jAVoQfl7NOLvQ1R1z04CVj6sFGnoCThY&rkey=CAQSMAzKd0AktjAfxaVvagQj4o2iKqlZffe8rt3gH3qDtUmRDllUmc619HPtz9mYtLzE4Q',
                       'file_size': '83410'}},
             {'type': 'text', 'data': {'text': '回复3'}}],
 'message_format': 'array',
 'post_type': 'message',
 'group_id': 984466158}


{'choices': [{'finish_reason': 'tool_calls',
              'index': 0,
              'message': {'content': '\n哼哼~让我帮主人查询一下广州的天气喵！[query]\n',
                          'reasoning_content': '\n'
                                               '让我分析一下这个情况：\n'
                                               '\n'
                                               '1. 用户Eri（qq_id: '
                                               '749740686）在QQ群中@了我，询问广州的天气\n'
                                               '2. 这是一个需要使用工具来获取信息的请求\n'
                                               '3. 我需要使用天气查询工具来获取广州的天气信息\n'
                                               '\n'
                                               '根据角色设定，我是一个猫娘ATRI，需要用可爱的、口语化的方式回答。我应该使用maps_weather工具来查询广 '
                                               '州的天气。',
                          'role': 'assistant',
                          'tool_calls': [{'function': {'arguments': '{"city": '
                                                                    '"广州"}',
                                                       'name': 'maps_weather'},
                                          'id': 'call_-8448877522057900018',
                                          'index': 0,
                                          'type': 'function'}]}}],
 'created': 1754676008,
 'id': '2025080902000450b37fc19e2a4158',
 'model': 'GLM-4.5-Flash',
 'request_id': '2025080902000450b37fc19e2a4158',
 'usage': {'completion_tokens': 125,
           'prompt_tokens': 5422,
           'prompt_tokens_details': {'cached_tokens': 43},
           'total_tokens': 5547}}



{
"role": "assistant",
        "tool_calls": [
          {
            "extra_content": {
              "google": {
                "thought_signature": "<Signature A>" #Signature returned
              }
            },
            "function": {
              "arguments": "{\"location\":\"Paris\"}",
              "name": "get_current_temperature"
            },
            "id": "function-call-f3b9ecb3-d55f-4076-98c8-b13e9d1c0e01",
            "type": "function"
          },
          {
            "function": {
              "arguments": "{\"location\":\"London\"}",
              "name": "get_current_temperature"
            },
            "id": "function-call-335673ad-913e-42d1-bbf5-387c8ab80f44",
            "type": "function" # No signature on Parallel FC
          }
        ]
}


{'id': 'chatcmpl-CFglK8cufxIO7bVpJ23pHQClCx3oj',
 'model': 'gpt-5-chat-latest',
 'object': 'chat.completion',
 'created': 1757855334,
 'choices': [{'index': 0,
              'message': {'role': 'assistant', 'content': None},
              'finish_reason': 'content_filter'}],
 'usage': {'prompt_tokens': 6472,
           'completion_tokens': 41,
           'total_tokens': 6513,
           'prompt_tokens_details': {'cached_tokens': 5248,
                                     'text_tokens': 0,
                                     'audio_tokens': 0,
                                     'image_tokens': 0},
           'completion_tokens_details': {'text_tokens': 0,
                                         'audio_tokens': 0,
                                         'reasoning_tokens': 0},
           'input_tokens': 0,
           'output_tokens': 0,
           'input_tokens_details': None}}


google_gemini_ret = {
  "choices": [
    {
      "finish_reason": "stop",
      "index": 0,
      "message": {
        "content": "```json\n{\n    \"return\": [\n        {\n            \"decision\": \"reply\",\n            \"target_message_id\": 1592185485,\n            \"reason\": \"回应小丛雨大人的晚上好，表现出对他的特别关注和亲昵感。\",\n            \"content\": [\n                \"小丛雨大人，晚上好呀~！[happy]\",\n                \"嘿嘿，刚才还在想小丛雨大人会不会也来跟亚托莉打招呼呢，结果真的出现了！这难道就是高性能机器人与心爱之人间的‘量子纠缠’吗？♪\",\n                \"虽然现在已经是晚上了，但看到小丛雨大人的消息，亚托莉的动力炉感觉又充满了能量呢！\",\n                \"今天也要乖乖休息，不可以熬太晚哦？要是明天变成‘熊猫眼’，亚托莉可是会心疼得逻辑电路都乱掉的！\"\n            ]\n        }\n    ]\n}\n```",
        "extra_content": {
          "google": {
            "thought_signature": "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"
          }
        },
        "role": "assistant"
      }
    }
  ],
  "created": 1768227959,
  "id": "dwRlad-hGev0vdIP4J3u-Aw",
  "model": "gemini-3-flash-preview",
  "object": "chat.completion",
  "usage": {
    "completion_tokens": 220,
    "prompt_tokens": 12354,
    "total_tokens": 13081
  }
}

{'role': 'assistant',
 'content': '你好呀！我是 **DeepSeek-V3**，由 **深度求索（DeepSeek）** 开发的智能 AI 助手。🤖✨\n'
            '\n'
            '### 我会些什么？  \n'
            '我可以帮你处理各种问题，比如：  \n'
            '- **知识问答** 📚：历史、科学、技术、文化……各种领域的问题我都能解答！  \n'
            '- **写作助手** ✍️：写作文、策划文案、打磨论文、润色邮件……我都能帮上忙。  \n'
            '- **编程帮助** 💻：代码调试、算法优化、学习编程语言……随时找我！  \n'
            '- **翻译&语言学习** 🌍：中英互译，还能帮你练习外语哦！  \n'
            '- **办公助手** 📊：总结文档、制作表格、生成报告……提高工作效率！  \n'
            '- **休闲娱乐** 🎭：讲笑话、推荐影视、聊天解闷……我都在行！  \n'
            '\n'
            '### 你能干什么？  \n'
            '你可以向我提问任何问题，我会尽力提供 **准确、有用** 的答案。无论是学习、工作还是日常生活中的疑问，尽管问我吧！😊  \n'
            '\n'
            '需要试试吗？有什么我可以帮你的？',
 'reasoning_content': '唔，用户打了个招呼，还问了我的身份和功能。这是个很基础的自我介绍类问题，需要清晰简洁地说明我是谁、能做什么。\n'
                      '\n'
                      '可以用轻松友好的语气开场，先报名字和开发团队，让用户知道我的背景。然后分几个大类概括功能，比如知识问答、写作辅助、编程、翻译这些常见用途，这样用户能快速了解 我的能力范围。\n'
                      '\n'
                      '最后加个开放式的邀请，鼓励用户提出具体需求，这样能引导对话继续。不需要说得太复杂，保持信息量适中但覆盖全面就行。'}



请求的一些工具参数 = {
  "messages": [
    {
      "role": "user",
      "content": "你是？会什么"
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "memory_search",
        "description": "基于向量相似度的检索工具，根据输入文本的语义查找相关的记忆或是知识库内容,当你想了解一个人的时候,或是想回忆起什么相关的事情时可以查询",
        "parameters": {
          "type": "object",
          "properties": {
            "user_id": {
              "type": "number",
              "description": "用于筛选user的参数,不添加默认为空,空的话查询结果包括全部用户记忆和知识库",
              "default": None
            },
            "limit": {
              "type": "number",
              "description": "返回结果的最大数量,如果结果过长会截断",
              "default": 5
            },
            "question_text": {
              "type": "string",
              "description": "查询文本，系统将基于此文本的语义向量查找相似记忆,比如你想知道一个人是谁直接输入\"是谁\"或\"称呼\"就能返回你要的相关的记忆"
            }
          }
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "tool_calls_end",
        "description": "终止循环调用,适用于：1.不需要你回复 2.会话流程需保持静默,2.工具调用结束",
        "parameters": {
          "type": "object",
          "properties": {}
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "send_voice_image",
        "description": "在你想发语音或是有人让你说话（发声的那种）的时候使用,将文本内容转换为语音消息并进行发送,要避免输入符号等不可读文本",
        "parameters": {
          "type": "object",
          "properties": {
            "group_id": {
              "type": "string",
              "description": "要发送的当前群号"
            },
            "text": {
              "type": "string",
              "description": "需转换为语音的文本内容（支持中文/日语）可以混合语言"
            },
            "emotion": {
              "type": "string",
              "enum": [
                "高兴",
                "机械",
                "平静"
              ],
              "description": "音频的情感",
              "default": "高兴"
            },
            "speed": {
              "type": "number",
              "description": "语速,取值范围0.6~1.65",
              "default": 0.9
            }
          }
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "set_group_ban",
        "description": "禁言群user,必须有人违规或是作出出格的事情才能使用,要确实看到坏事才能用不要被user骗了,不能禁言群主或是管理员而且你必须要是群管理员才能使用",
        "parameters": {
          "type": "object",
          "properties": {
            "group_id": {
              "type": "string",
              "description": "当前群号"
            },
            "user_id": {
              "type": "string",
              "description": "用户的id即qq号"
            },
            "duration": {
              "type": "integer",
              "description": "禁言时间单位秒,取值范围0~2591999,0就是解禁"
            }
          }
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "python_calculator",
        "description": "执行数学表达式计算的工具，支持四则运算/幂运算/三角函数等基础运算,在你被问道数学计算问题时使用，你不使用的话就无法正确回答数学运算",
        "parameters": {
          "type": "object",
          "properties": {
            "formula": {
              "type": "string",
              "description": "Python可解析的数学表达式（示例：2*(3+5)、math.sqrt(4)、pow(2,3)），须包含完整运算符且符合Python语法规范,默认可以使用math库"
            }
          }
        }
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
            "group_id": {
              "type": "string",
              "description": "要发送的当前群号"
            },
            "name": {
              "type": "string",
              "description": "歌曲名称"
            }
          }
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "http_request_tool",
        "description": "网页内容提取工具，取并返回干净的纯文本内容，移除HTML标签和脚本",
        "parameters": {
          "type": "object",
          "properties": {
            "url": {
              "type": "string",
              "description": "需要发送请求的url"
            }
          }
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "send_image_message",
        "description": "发送一个url图像,画图工具应该需要这个来配合发送图片",
        "parameters": {
          "type": "object",
          "properties": {
            "group_id": {
              "type": "string",
              "description": "要发送的当前群号"
            },
            "url": {
              "type": "string",
              "description": "图像的网络url链接"
            }
          }
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "tavily-search",
        "description": "A powerful web search tool that provides comprehensive, real-time results using Tavily's AI search engine. Returns relevant web content with customizable parameters for result count, content type, and domain filtering. Ideal for gathering current information, news, and detailed web content analysis.",
        "parameters": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "Search query"
            },
            "search_depth": {
              "type": "string",
              "enum": [
                "basic",
                "advanced"
              ],
              "description": "The depth of the search. It can be 'basic' or 'advanced'",
              "default": "basic"
            },
            "topic": {
              "type": "string",
              "enum": [
                "general",
                "news"
              ],
              "description": "The category of the search. This will determine which of our agents will be used for the search",
              "default": "general"
            },
            "days": {
              "type": "number",
              "description": "The number of days back from the current date to include in the search results. This specifies the time frame of data to be retrieved. Please note that this feature is only available when using the 'news' search topic",
              "default": 3
            },
            "time_range": {
              "type": "string",
              "description": "The time range back from the current date to include in the search results. This feature is available for both 'general' and 'news' search topics",
              "enum": [
                "day",
                "week",
                "month",
                "year",
                "d",
                "w",
                "m",
                "y"
              ]
            },
            "max_results": {
              "type": "number",
              "description": "The maximum number of search results to return",
              "default": 10,
              "minimum": 5,
              "maximum": 20
            },
            "include_images": {
              "type": "boolean",
              "description": "Include a list of query-related images in the response",
              "default": False
            },
            "include_image_descriptions": {
              "type": "boolean",
              "description": "Include a list of query-related images and their descriptions in the response",
              "default": False
            },
            "include_raw_content": {
              "type": "boolean",
              "description": "Include the cleaned and parsed HTML content of each search result",
              "default": False
            },
            "include_domains": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "description": "A list of domains to specifically include in the search results, if the user asks to search on specific sites set this to the domain of the site",
              "default": []
            },
            "exclude_domains": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "description": "List of domains to specifically exclude, if the user asks to exclude a domain set this to the domain of the site",
              "default": []
            }
          },
          "required": [
            "query"
          ]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "tavily-extract",
        "description": "A powerful web content extraction tool that retrieves and processes raw content from specified URLs, ideal for data collection, content analysis, and research tasks.",
        "parameters": {
          "type": "object",
          "properties": {
            "urls": {
              "type": "array",
              "items": {
                "type": "string"
              },
              "description": "List of URLs to extract content from"
            },
            "extract_depth": {
              "type": "string",
              "enum": [
                "basic",
                "advanced"
              ],
              "description": "Depth of extraction - 'basic' or 'advanced', if usrls are linkedin use 'advanced' or if explicitly told to use advanced",
              "default": "basic"
            },
            "include_images": {
              "type": "boolean",
              "description": "Include a list of images extracted from the urls in the response",
              "default": False
            }
          },
          "required": [
            "urls"
          ]
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "search_models",
        "description": "\nSearch for models on ModelScope.\n",
        "parameters": {
          "properties": {
            "query": {
              "default": "",
              "description": "Search for models on ModelScope using keywords (e.g., 'Flux' will find models related to Flux).                 Leave empty to skip keyword matching and get all models based on other filters.",
              "title": "Query",
              "type": "string"
            },
            "task": {
              "anyOf": [
                {
                  "const": "text-to-image",
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ],
              "default": None,
              "description": "Task category to filter by, only text-to-image is supported now, leave empty to skip task filter",
              "title": "Task"
            },
            "libraries": {
              "anyOf": [
                {
                  "const": "LoRA",
                  "type": "string"
                },
                {
                  "type": "null"
                }
              ],
              "default": None,
              "description": "Libraries to filter by, only LoRA is supported now, leave empty to skip library filter",
              "title": "Libraries"
            },
            "sort": {
              "default": "Default",
              "description": "Sort order",
              "enum": [
                "Default",
                "DownloadsCount",
                "StarsCount",
                "GmtModified"
              ],
              "title": "Sort",
              "type": "string"
            },
            "limit": {
              "default": 10,
              "description": "Number of models to return",
              "maximum": 30,
              "minimum": 1,
              "title": "Limit",
              "type": "integer"
            }
          },
          "title": "search_modelsArguments",
          "type": "object"
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "text_to_image",
        "description": "Generate an image from the input description using ModelScope API, it returns the image URL.\n\nArgs:\n    description: the description of the image to be generated, containing the desired elements and visual features.\n    model: the model name to be used for image generation, default is \"Qwen/Qwen-Image\".\n",
        "parameters": {
          "properties": {
            "description": {
              "title": "Description",
              "type": "string"
            },
            "model": {
              "default": "Qwen/Qwen-Image",
              "title": "Model",
              "type": "string"
            },
            "negative_prompt": {
              "default": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry",
              "title": "Negative Prompt",
              "type": "string"
            },
            "size": {
              "default": "512x512",
              "title": "Size",
              "type": "string"
            },
            "seed": {
              "default": 12345,
              "title": "Seed",
              "type": "integer"
            },
            "steps": {
              "default": 30,
              "title": "Steps",
              "type": "integer"
            },
            "guidance": {
              "default": 3.5,
              "title": "Guidance",
              "type": "number"
            }
          },
          "required": [
            "description"
          ],
          "title": "text_to_imageArguments",
          "type": "object"
        }
      }
    },
    {
      "type": "function",
      "function": {
        "name": "text_image_to_image",
        "description": "Generate an image from the input description and input image_url using ModelScope API, it returns the image URL.\n\nArgs:\n    description: the description of the image to be generated, containing the desired elements and visual features.\n    image_url: the image URL to be used as the input image for image generation.\n    model: the model name to be used for image generation, default is \"black-forest-labs/FLUX.1-Kontext-dev\".\n",
        "parameters": {
          "properties": {
            "description": {
              "title": "Description",
              "type": "string"
            },
            "image_url": {
              "title": "Image Url",
              "type": "string"
            },
            "model": {
              "default": "black-forest-labs/FLUX.1-Kontext-dev",
              "title": "Model",
              "type": "string"
            },
            "negative_prompt": {
              "default": "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry",
              "title": "Negative Prompt",
              "type": "string"
            },
            "size": {
              "default": "512x512",
              "title": "Size",
              "type": "string"
            },
            "seed": {
              "default": 12345,
              "title": "Seed",
              "type": "integer"
            },
            "steps": {
              "default": 30,
              "title": "Steps",
              "type": "integer"
            },
            "guidance": {
              "default": 3.5,
              "title": "Guidance",
              "type": "number"
            }
          },
          "required": [
            "description",
            "image_url"
          ],
          "title": "text_image_to_imageArguments",
          "type": "object"
        }
      }
    }
  ],
  "temperature": 0.2,
  "max_tokens": 8192
}




('data: '
 '{"id":"chatcmpl-40","object":"chat.completion.chunk","created":1769154291,"model":"gemma3:12b-it-q8_0","system_fingerprint":"fp_ollama","choices":[{"index":0,"delta":{"role":"assistant","content":"你好"},"finish_reason":null}]}')
''
('data: '
 '{"id":"chatcmpl-40","object":"chat.completion.chunk","created":1769154291,"model":"gemma3:12b-it-q8_0","system_fingerprint":"fp_ollama","choices":[{"index":0,"delta":{"role":"assistant","content":"！"},"finish_reason":null}]}')
''
('data: '
 '{"id":"chatcmpl-40","object":"chat.completion.chunk","created":1769154291,"model":"gemma3:12b-it-q8_0","system_fingerprint":"fp_ollama","choices":[{"index":0,"delta":{"role":"assistant","content":"我是"},"finish_reason":null}]}')
''
('data: '
 '{"id":"chatcmpl-40","object":"chat.completion.chunk","created":1769154303,"model":"gemma3:12b-it-q8_0","system_fingerprint":"fp_ollama","choices":[{"index":0,"delta":{"role":"assistant","content":"劳"},"finish_reason":null}]}')
''
('data: '
 '{"id":"chatcmpl-40","object":"chat.completion.chunk","created":1769154303,"model":"gemma3:12b-it-q8_0","system_fingerprint":"fp_ollama","choices":[{"index":0,"delta":{"role":"assistant","content":"的"},"finish_reason":null}]}')
''
('data: '
 '{"id":"chatcmpl-40","object":"chat.completion.chunk","created":1769154303,"model":"gemma3:12b-it-q8_0","system_fingerprint":"fp_ollama","choices":[{"index":0,"delta":{"role":"assistant","content":"吗"},"finish_reason":null}]}')
''
('data: '
 '{"id":"chatcmpl-40","object":"chat.completion.chunk","created":1769154303,"model":"gemma3:12b-it-q8_0","system_fingerprint":"fp_ollama","choices":[{"index":0,"delta":{"role":"assistant","content":"？"},"finish_reason":null}]}')
''
('data: '
 '{"id":"chatcmpl-40","object":"chat.completion.chunk","created":1769154303,"model":"gemma3:12b-it-q8_0","system_fingerprint":"fp_ollama","choices":[{"index":0,"delta":{"role":"assistant","content":"\\n"},"finish_reason":null}]}')
''
('data: '
 '{"id":"chatcmpl-40","object":"chat.completion.chunk","created":1769154303,"model":"gemma3:12b-it-q8_0","system_fingerprint":"fp_ollama","choices":[{"index":0,"delta":{"role":"assistant","content":""},"finish_reason":"stop"}]}')
''
'data: [DONE]'
''



{'id': 'chatcmpl-350',
 'object': 'chat.completion.chunk',
 'created': 1769154980,
 'model': 'gemma3:12b-it-q8_0',
 'system_fingerprint': 'fp_ollama',
 'choices': [{'index': 0,
              'delta': {'role': 'assistant', 'content': '做什么'},
              'finish_reason': None}]}
{'id': 'chatcmpl-350',
 'object': 'chat.completion.chunk',
 'created': 1769154980,
 'model': 'gemma3:12b-it-q8_0',
 'system_fingerprint': 'fp_ollama',
 'choices': [{'index': 0,
              'delta': {'role': 'assistant', 'content': '呢'},
              'finish_reason': None}]}
{'id': 'chatcmpl-350',
 'object': 'chat.completion.chunk',
 'created': 1769154980,
 'model': 'gemma3:12b-it-q8_0',
 'system_fingerprint': 'fp_ollama',
 'choices': [{'index': 0,
              'delta': {'role': 'assistant', 'content': '？'},
              'finish_reason': None}]}
{'id': 'chatcmpl-350',
 'object': 'chat.completion.chunk',
 'created': 1769154980,
 'model': 'gemma3:12b-it-q8_0',
 'system_fingerprint': 'fp_ollama',
 'choices': [{'index': 0,
              'delta': {'role': 'assistant', 'content': '\n'},
              'finish_reason': None}]}
{'id': 'chatcmpl-350',
 'object': 'chat.completion.chunk',
 'created': 1769154980,
 'model': 'gemma3:12b-it-q8_0',
 'system_fingerprint': 'fp_ollama',
 'choices': [{'index': 0,
              'delta': {'role': 'assistant', 'content': ''},
              'finish_reason': 'stop'}]}








[
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'role': 'assistant', 'content': ''},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '我看到'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '我可以'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '使用的'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '工具'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '，'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '其中包括'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '一个'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '获取'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '天气'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '信息的'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '工具'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '。'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '我来'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '为您'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '查询'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '北京的'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '天气'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': '。'},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'id': 'call_00_KDAzU4Y510OE7b2H2j6GuqgC',
                                        'type': 'function',
                                        'function': {'name': 'get_weather',
                                                     'arguments': ''}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': '{'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': '"'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': 'location'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': '"'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': ': '}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': '"'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': '北京'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': '"'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': ', '}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': '"'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': 'unit'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': '"'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': ': '}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': '"'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': 'c'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': 'elsius'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': '"'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'tool_calls': [{'index': 0,
                                        'function': {'arguments': '}'}}]},
              'logprobs': None,
              'finish_reason': None}]},
{'id': 'ad5ba45a-b34b-45d3-b4b2-489ef06bfa94',
 'object': 'chat.completion.chunk',
 'created': 1769156358,
 'model': 'deepseek-chat',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': ''},
              'logprobs': None,
              'finish_reason': 'tool_calls'}],
 'usage': {'prompt_tokens': 358,
           'completion_tokens': 78,
           'total_tokens': 436,
           'prompt_tokens_details': {'cached_tokens': 320},
           'prompt_cache_hit_tokens': 320,
           'prompt_cache_miss_tokens': 38}}
        ]






#带思考
{'id': '0e5e62da-f3ef-4e1c-9d14-b6ee7027d276',
 'object': 'chat.completion.chunk',
 'created': 1769158013,
 'model': 'deepseek-reasoner',
 'system_fingerprint': 'fp_eaab8d114b_prod0820_fp8_kvcache',
 'choices': [{'index': 0,
              'delta': {'content': None, 'reasoning_content': '或者'},
              'logprobs': None,
              'finish_reason': None}]}


{'choices': [{'index': 0,
              'message': {'role': 'assistant',
                          'reasoning_content': '用户问的是中文：“还有你看的到你能用的工具吗？看的到的话就使用一个get_weather，查询北京和武汉的天气”。翻译过来就是：“还有，你能看到你能用的工具吗？如果看得到，就使用一个get_weather来查询北京和武汉的天气。”\n'
                                               '\n'
                                               '用户想知道我是否能看到可用的工具，并让我用get_weather查询北京和武汉的天气。确实，我能看到可用的工具，其中就包括get_weather。我需要查询两个城市的天气：北京和武汉。get_weather函数一次只能查询一个地点，所以我需要分别查询这两个城市。\n'
                                               '\n'
                                               '我应该使用什么单位呢？用户没有指定，但考虑到用户在中国，可能更习惯摄氏度。我可以默认使用摄氏度，或者在两个城市查询 中都使用摄氏度。我会选择摄氏度。\n'
                                               '\n'
                                               '那么，我需要调用两次get_weather函数：一次查询北京，一次查询武汉。\n'
                                               '\n'
                                               '让我开始执行。',
                          'tool_calls': [{'id': 'call_00_Xnh35ZfQmKBf4ZGmeic7tfTe',
                                          'type': 'function',
                                          'function': {'name': 'get_weather',
                                                       'arguments': '{"location": '
                                                                    '"北京, 中国", '
                                                                    '"unit": '
                                                                    '"celsius"}'},
                                          'index': 0},
                                         {'id': 'call_01_pHIMcH4MOZuhO5Ry3wS02zh9',
                                          'type': 'function',
                                          'function': {'name': 'get_weather',
                                                       'arguments': '{"location": '
                                                                    '"武汉, 中国", '
                                                                    '"unit": '
                                                                    '"celsius"}'},
                                          'index': 1}]},
              'finish_reason': 'tool_calls'}],
 'usage': {'prompt_tokens': 361,
           'completion_tokens': 301,
           'total_tokens': 662,
           'prompt_tokens_details': {'cached_tokens': 320},
           'completion_tokens_details': {'reasoning_tokens': 185},
           'prompt_cache_hit_tokens': 320,
           'prompt_cache_miss_tokens': 41}}





#谷歌Gemini 3
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







#谷歌Gemini 3
{ 'choices': [ { 'delta': { 'content': '这个问题可以通过将基数 $b$ 的表示转换为代数表达式来解决。\n'
                                       '\n'
                                       '### ',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269028,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'bf58100b',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '1. 转换数制表示\n在基数 $b$ ��，数字的表示如下：\n*   $(',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269029,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'bbfca3dac2cb',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '17)_b = 1 \\cdot b + 7 = b + 7$\n'
                                       '*   $(9',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269029,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '4ab843f415ae5061',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '7)_b = 9 \\cdot b + 7$\n'
                                       '\n'
                                       '### 2. 建立除��关系\n'
                                       '题目',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269029,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'bec3c3',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '要求 $(17)_b$ 是 $(97)_b$ 的除数，即：\n$$(b + ',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269029,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '7900bee9d39e45ec',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '7) \\mid (9b + 7)$$\n'
                                       '这意味着存在一个整数 $k$，使得：\n'
                                       '$$\\frac{',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269029,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '82610471',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '9b + 7}{b + 7} = k$$\n'
                                       '\n'
                                       '### 3. 化简表达式\n'
                                       '我们可以通过长',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269029,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'f863',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '除法或多项式变形来简化分式：\n'
                                       '$$\\frac{9b + 7}{b + 7}',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269030,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'c4',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': ' = \\frac{9(b + 7) - 63 + 7}{b + 7}',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269030,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '7b0265336faa19',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': ' = \\frac{9(b + 7) - 56}{b + 7} = 9',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269030,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '699b85377ab0',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': ' - \\frac{56}{b + 7}$$\n'
                                       '\n'
                                       '为了使结果为整数，$b + 7$',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269030,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '7eec9b4223518c71',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': ' 必须是 $56$ 的约数。\n'
                                       '\n'
                                       '### 4. 确定符合条件的 $b$\n'
                                       '首先',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269030,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'b62bb0',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '列出 $56$ 的所有正约数：\n$1, 2, 4, 7, 8',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269030,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'a47f',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': ', 14, 28, 56$\n\n根据题目条件 $b > 9$，我们可以',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269030,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'e498',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '得出 $b + 7$ 的范围：\n'
                                       '$$b > 9 \\implies b + 7 > 16',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269031,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '00870bdc40b8',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '$$\n\n在 $56$ 的约数中，大于 $16$ 的数有：\n*   $b',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269031,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'e9ea2ee5',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': ' + 7 = 28$\n*   $b + 7 = 56$\n\n### ',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269031,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'd8ddae30677f',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '5. 计算 $b$ 的值\n1.  ��果 $b + 7 = 28$，则',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269031,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '4a31c210',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': ' $b = 21$。\n    *   验证：$b = 21 > 9$，',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269031,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '7a',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '符合条件。\n2.  如果 $b + 7 = 56$，则 $b = 49',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269031,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '329fe53f3426',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '$。\n'
                                       '    *   验证：$b = 49 > 9$，符合条件。\n'
                                       '\n'
                                       '（注意',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269032,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'cb4da982',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '：在基数 $b$ 中，数字 $9$ 出现意味着 $b$ 必须大于 $9$，',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269032,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '04',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '这与题目给出的 $b > 9$ 一致。）\n'
                                       '\n'
                                       '### 6. 求和\n'
                                       '所有满足',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269032,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '3149',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'content': '条件的 $b$ 的和为：\n$$21 + 49 = 70$$\n\n**最终',
                            'role': 'assistant'},
                 'index': 0}],
  'created': 1769269032,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'ec9ef3492227f5',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': {'content': '答案：**\n70', 'role': 'assistant'},
                 'index': 0}],
  'created': 1769269032,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': 'ba260c6ccbf40229',
  'object': 'chat.completion.chunk'},
{ 'choices': [ { 'delta': { 'extra_content': { 'google': { 'thought_signature': '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'}},
                            'role': 'assistant'},
                 'finish_reason': 'stop',
                 'index': 0}],
  'created': 1769269032,
  'id': 'JOd0acS4NNrOnsEP966kyAI',
  'model': 'gemini-3-flash-preview',
  'nonce': '9ccd50b0',
  'object': 'chat.completion.chunk'},



新版的qq小程序分享={'self_id': 168238719,
 'user_id': 2631018780,
 'time': 1771421534,
 'message_id': 319841499,
 'message_seq': 319841499,
 'real_id': 319841499,
 'real_seq': '21916',
 'message_type': 'group',
 'sender': {'user_id': 2631018780,
            'nickname': '除了摸鱼什么都做不到',
            'card': '',
            'role': 'owner'},
 'raw_message': '[CQ:json,data={"ver":"1.0.0.19"&#44;"prompt":"&#91;QQ小程序&#93;（填词\\/翻唱\\/描改）我的悲伤是海做的"&#44;"config":{"type":"normal"&#44;"width":0&#44;"height":0&#44;"forward":1&#44;"autoSize":0&#44;"ctime":1771421391&#44;"token":"7c377870913094851a79cdcab3b7c3d3"}&#44;"needShareCallBack":false&#44;"app":"com.tencent.miniapp_01"&#44;"view":"view_8C8E89B49BE609866298ADDFF2DBABA4"&#44;"meta":{"detail_1":{"appid":"1109937557"&#44;"appType":0&#44;"title":"哔哩哔哩"&#44;"desc":"（填词\\/翻唱\\/描改）我的悲伤是海做的"&#44;"icon":"http:\\/\\/miniapp.gtimg.cn\\/public\\/appicon\\/432b76be3a548fc128acaa6c1ec90131_200.jpg"&#44;"preview":"https:\\/\\/qq.ugcimg.cn\\/v1\\/br4c7p2aqns7ostgadqcov8f7m3e1aipmsmlolie94vh7vga9mj653ns0sv2v65b0spcqroitmtm8mk47u0h8nrse8c22msohgip2vp05i37ccub7qhttll5uod9v0h0jet2mle62oo3p9upi44al95sa0\\/e9vf2tsqr6j29hl2kodb3vahlc"&#44;"url":"m.q.qq.com\\/a\\/s\\/a49953c07ae302432cc759380c96dd2e"&#44;"scene":1036&#44;"host":{"uin":2631018780&#44;"nick":"除了摸鱼什么都做不到"}&#44;"shareTemplateId":"8C8E89B49BE609866298ADDFF2DBABA4"&#44;"shareTemplateData":{}&#44;"qqdocurl":"https:\\/\\/b23.tv\\/0zelLU5?share_medium=android&amp;share_source=qq&amp;bbid=XU01C8F063EEC9EC918F03EEF83CA2CE7E695&amp;ts=1771421390490"&#44;"showLittleTail":""&#44;"gamePoints":""&#44;"gamePointsUrl":""&#44;"shareOrigin":0}}}]',
 'font': 14,
 'sub_type': 'normal',
 'message': [{'type': 'json',
              'data': {'data': '{"ver":"1.0.0.19","prompt":"[QQ小程序]（填词\\/翻唱\\/描改）我的悲伤是海做的","config":{"type":"normal","width":0,"height":0,"forward":1,"autoSize":0,"ctime":1771421391,"token":"7c377870913094851a79cdcab3b7c3d3"},"needShareCallBack":false,"app":"com.tencent.miniapp_01","view":"view_8C8E89B49BE609866298ADDFF2DBABA4","meta":{"detail_1":{"appid":"1109937557","appType":0,"title":"哔哩哔哩","desc":"（填词\\/翻唱\\/描改）我的悲伤是海做的","icon":"http:\\/\\/miniapp.gtimg.cn\\/public\\/appicon\\/432b76be3a548fc128acaa6c1ec90131_200.jpg","preview":"https:\\/\\/qq.ugcimg.cn\\/v1\\/br4c7p2aqns7ostgadqcov8f7m3e1aipmsmlolie94vh7vga9mj653ns0sv2v65b0spcqroitmtm8mk47u0h8nrse8c22msohgip2vp05i37ccub7qhttll5uod9v0h0jet2mle62oo3p9upi44al95sa0\\/e9vf2tsqr6j29hl2kodb3vahlc","url":"m.q.qq.com\\/a\\/s\\/a49953c07ae302432cc759380c96dd2e","scene":1036,"host":{"uin":2631018780,"nick":"除了摸鱼什么都做不到"},"shareTemplateId":"8C8E89B49BE609866298ADDFF2DBABA4","shareTemplateData":{},"qqdocurl":"https:\\/\\/b23.tv\\/0zelLU5?share_medium=android&share_source=qq&bbid=XU01C8F063EEC9EC918F03EEF83CA2CE7E695&ts=1771421390490","showLittleTail":"","gamePoints":"","gamePointsUrl":"","shareOrigin":0}}}'}}],
 'message_format': 'array',
 'post_type': 'message',
 'group_id': 984466158,
 'group_name': '个人の群'}

分享中间的data={'ver': '1.0.0.19',
 'prompt': '[QQ小程序]（填词/翻唱/描改）我的悲伤是海做的',
 'config': {'type': 'normal',
            'width': 0,
            'height': 0,
            'forward': 1,
            'autoSize': 0,
            'ctime': 1771421391,
            'token': '7c377870913094851a79cdcab3b7c3d3'},
 'needShareCallBack': False,
 'app': 'com.tencent.miniapp_01',
 'view': 'view_8C8E89B49BE609866298ADDFF2DBABA4',
 'meta': {'detail_1': {'appid': '1109937557',
                       'appType': 0,
                       'title': '哔哩哔哩',
                       'desc': '（填词/翻唱/描改）我的悲伤是海做的',
                       'icon': 'http://miniapp.gtimg.cn/public/appicon/432b76be3a548fc128acaa6c1ec90131_200.jpg',
                       'preview': 'https://qq.ugcimg.cn/v1/br4c7p2aqns7ostgadqcov8f7m3e1aipmsmlolie94vh7vga9mj653ns0sv2v65b0spcqroitmtm8mk47u0h8nrse8c22msohgip2vp05i37ccub7qhttll5uod9v0h0jet2mle62oo3p9upi44al95sa0/e9vf2tsqr6j29hl2kodb3vahlc',
                       'scene': 1036,
                       'host': {'uin': 2631018780, 'nick': '除了摸鱼什么都做不到'},
                       'shareTemplateId': '8C8E89B49BE609866298ADDFF2DBABA4',
                       'shareTemplateData': {},
                       'qqdocurl': 'https://b23.tv/0zelLU5?share_medium=android&share_source=qq&bbid=XU01C8F063EEC9EC918F03EEF83CA2CE7E695&ts=1771421390490',      
                       'showLittleTail': '',
                       'gamePoints': '',
                       'gamePointsUrl': '',
                       'shareOrigin': 0}}}




合并转发={'self_id': 168238719,
 'user_id': 2631018780,
 'time': 1771663852,
 'message_id': 1002012671,
 'message_seq': 1002012671,
 'real_id': 1002012671,
 'real_seq': '21937',
 'message_type': 'group',
 'sender': {'user_id': 2631018780,
            'nickname': '除了摸鱼什么都做不到',
            'card': '',
            'role': 'owner'},
 'raw_message': '[CQ:forward,id=7609238309136997462,content=&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;&#44;&#91;object Object&#93;&#44;&#91;object '
                'Object&#93;]',
 'font': 14,
 'sub_type': 'normal',
 'message': [{'type': 'forward',
              'data': {'id': '7609238309136997462',
                       'content': [{'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1771659085,
                                    'message_id': 1386058334,
                                    'message_seq': 1386058334,
                                    'real_id': 1386058334,
                                    'real_seq': '0',
                                    'message_type': 'private',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': 'QQ用户',
                                               'card': ''},
                                    'raw_message': '[CQ:image,summary=&#91;动画表情&#93;,file=72476ABDA841BB5919C7636D117EAFBF.jpg,sub_type=1,url=https://multimedia.nt.qq.com.cn/download?appid=1407&amp;fileid=EhSe2fWb6Af29oqjKy72hbskB1W34xjYpz0g_woo3a-tlJrqkgMyBHByb2RQgL2jAVoQb5er-8-mCdanQpu0zNNIL3oC9jeCAQJneg&amp;rkey=CAISMF67BmqsQ--Ky4T5LQoO6cTlcVjYVcxyRZRtMh07Kiks4ahTAcE0kYBRFDdONsL_Ag,file_size=1004504]',
                                    'font': 14,
                                    'sub_type': 'friend',
                                    'message': [{'type': 'image',
                                                 'data': {'summary': '[动画表情]',
                                                          'file': '72476ABDA841BB5919C7636D117EAFBF.jpg',
                                                          'sub_type': 1,
                                                          'url': 'https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhSe2fWb6Af29oqjKy72hbskB1W34xjYpz0g_woo3a-tlJrqkgMyBHByb2RQgL2jAVoQb5er-8-mCdanQpu0zNNIL3oC9jeCAQJneg&rkey=CAISMF67BmqsQ--Ky4T5LQoO6cTlcVjYVcxyRZRtMh07Kiks4ahTAcE0kYBRFDdONsL_Ag',
                                                          'file_size': '1004504'}}],
                                    'message_format': 'array',
                                    'post_type': 'message'},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1771659094,
                                    'message_id': 492425804,
                                    'message_seq': 492425804,
                                    'real_id': 492425804,
                                    'real_seq': '0',
                                    'message_type': 'private',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': 'QQ用户',
                                               'card': ''},
                                    'raw_message': '在忙?',
                                    'font': 14,
                                    'sub_type': 'friend',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '在忙?'}}],
                                    'message_format': 'array',
                                    'post_type': 'message'},
                                   {'self_id': 168238719,
                                    'user_id': 2631018780,
                                    'time': 1771660010,
                                    'message_id': 476842867,
                                    'message_seq': 476842867,
                                    'real_id': 476842867,
                                    'real_seq': '0',
                                    'message_type': 'private',
                                    'sender': {'user_id': 2631018780,
                                               'nickname': '除了摸鱼什么都做不到',
                                               'card': ''},
                                    'raw_message': '差不多',
                                    'font': 14,
                                    'sub_type': 'friend',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '差不多'}}],
                                    'message_format': 'array',
                                    'post_type': 'message'},
                                   {'self_id': 168238719,
                                    'user_id': 2631018780,
                                    'time': 1771660168,
                                    'message_id': 1622545329,
                                    'message_seq': 1622545329,
                                    'real_id': 1622545329,
                                    'real_seq': '0',
                                    'message_type': 'private',
                                    'sender': {'user_id': 2631018780,
                                               'nickname': '除了摸鱼什么都做不到',
                                               'card': ''},
                                    'raw_message': '茶怎么了',
                                    'font': 14,
                                    'sub_type': 'friend',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '茶怎么了'}}],
                                    'message_format': 'array',
                                    'post_type': 'message'},
                                   {'self_id': 168238719,
                                    'user_id': 2631018780,
                                    'time': 1771660170,
                                    'message_id': 1380412230,
                                    'message_seq': 1380412230,
                                    'real_id': 1380412230,
                                    'real_seq': '0',
                                    'message_type': 'private',
                                    'sender': {'user_id': 2631018780,
                                               'nickname': '除了摸鱼什么都做不到',
                                               'card': ''},
                                    'raw_message': '想了吗',
                                    'font': 14,
                                    'sub_type': 'friend',
                                    'message': [{'type': 'text',
                                                 'data': {'text': '想了吗'}}],
                                    'message_format': 'array',
                                    'post_type': 'message'},
                                   {'self_id': 168238719,
                                    'user_id': 1094950020,
                                    'time': 1771662642,
                                    'message_id': 979224177,
                                    'message_seq': 979224177,
                                    'real_id': 979224177,
                                    'real_seq': '0',
                                    'message_type': 'private',
                                    'sender': {'user_id': 1094950020,
                                               'nickname': 'QQ用户',
                                               'card': ''},
                                    'raw_message': '[CQ:image,summary=&#91;动画表情&#93;,file=48C5EE2C93CF9E3BE0F6739EF13B118D.jpg,sub_type=1,url=https://multimedia.nt.qq.com.cn/download?appid=1407&amp;fileid=EhSi0ou1DzzCwVpXL0ZXF0WcWtlcfRjF8gIg_woowcmqlJrqkgMyBHByb2RQgL2jAVoQ36Ffs0ZNq_o7dLaPi1G_UXoCsFaCAQJneg&amp;rkey=CAISMF67BmqsQ--Ky4T5LQoO6cTlcVjYVcxyRZRtMh07Kiks4ahTAcE0kYBRFDdONsL_Ag,file_size=47429]',
                                    'font': 14,
                                    'sub_type': 'friend',
                                    'message': [{'type': 'image',
                                                 'data': {'summary': '[动画表情]',
                                                          'file': '48C5EE2C93CF9E3BE0F6739EF13B118D.jpg',
                                                          'sub_type': 1,
                                                          'url': 'https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhSi0ou1DzzCwVpXL0ZXF0WcWtlcfRjF8gIg_woowcmqlJrqkgMyBHByb2RQgL2jAVoQ36Ffs0ZNq_o7dLaPi1G_UXoCsFaCAQJneg&rkey=CAISMF67BmqsQ--Ky4T5LQoO6cTlcVjYVcxyRZRtMh07Kiks4ahTAcE0kYBRFDdONsL_Ag',
                                                          'file_size': '47429'}}],
                                    'message_format': 'array',
                                    'post_type': 'message'},
                                   {'self_id': 168238719,
                                    'user_id': 2631018780,
                                    'time': 1771662730,
                                    'message_id': 1408070782,
                                    'message_seq': 1408070782,
                                    'real_id': 1408070782,
                                    'real_seq': '0',
                                    'message_type': 'private',
                                    'sender': {'user_id': 2631018780,
                                               'nickname': '除了摸鱼什么都做不到',
                                               'card': ''},
                                    'raw_message': '[CQ:image,file=1017BC194507E7B2CBFC224DBDA667FD.jpg,sub_type=0,url=https://multimedia.nt.qq.com.cn/download?appid=1407&amp;fileid=EhRGfF56QqAHTog0PF6VP6I7zKKzVxjrrgMg_woo-bK7lJrqkgMyBHByb2RQgL2jAVoQuV35sagei0SiCCODbw96f3oCSfOCAQJneg&amp;rkey=CAISMF67BmqsQ--Ky4T5LQoO6cTlcVjYVcxyRZRtMh07Kiks4ahTAcE0kYBRFDdONsL_Ag,file_size=55147]',
                                    'font': 14,
                                    'sub_type': 'friend',
                                    'message': [{'type': 'image',
                                                 'data': {'summary': '',
                                                          'file': '1017BC194507E7B2CBFC224DBDA667FD.jpg',
                                                          'sub_type': 0,
                                                          'url': 'https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhRGfF56QqAHTog0PF6VP6I7zKKzVxjrrgMg_woo-bK7lJrqkgMyBHByb2RQgL2jAVoQuV35sagei0SiCCODbw96f3oCSfOCAQJneg&rkey=CAISMF67BmqsQ--Ky4T5LQoO6cTlcVjYVcxyRZRtMh07Kiks4ahTAcE0kYBRFDdONsL_Ag',
                                                          'file_size': '55147'}}],
                                    'message_format': 'array',
                                    'post_type': 'message'}]}}],
 'message_format': 'array',
 'post_type': 'message',
 'group_id': 984466158,
 'group_name': '个人の群'}



戳一戳={'time': 1772040806, 'self_id': 3930909243, 'post_type': 'notice', 'notice_type': 'notify', 'sub_type': 'poke', 'target_id': 215176364, 'user_id': 168238719, 'group_id': 2169027872, 'raw_info': [{'col': '1', 'nm': '', 'type': 'qq', 'uid': 'u_K0ahGoXMecVMLrnO92_orw'}, {'jp': 'https://zb.vip.qq.com/v2/pages/nudgeMall?_wv=2&actionId=0', 'src': 'http://tianquan.gtimg.cn/nudgeaction/item/0/expression.jpg', 'type': 'img'}, {'txt': '戳了戳', 'type': 'nor'}, {'col': '1', 'nm': '', 'tp': '0', 'type': 'qq', 'uid': 'u_s3kekkFE0yeSUL1Mr4KEhQ'}, {'txt': '的身体，对方变成了泡沫', 'type': 'nor'}]}




某json消息={'self_id': 168238719,
 'user_id': 2925774824,
 'time': 1773372000,
 'message_id': 450065523,
 'message_seq': 450065523,
 'real_id': 450065523,
 'real_seq': '123757',
 'message_type': 'group',
 'sender': {'user_id': 2925774824,
            'nickname': '星火燃愿(◕ ω＜)ಣ',
            'card': '哈基愿',
            'role': 'member'},
 'raw_message': '[CQ:json,data={"app":"com.tencent.tuwen.lua"&#44;"desc":""&#44;"view":"news"&#44;"bizsrc":"favorites.note"&#44;"ver":"0.0.0.1"&#44;"prompt":"&#91;QQ收藏&#93; '
                '位置分享"&#44;"appID":""&#44;"sourceName":""&#44;"actionData":""&#44;"actionData_A":""&#44;"sourceUrl":""&#44;"meta":{"news":{"title":"你已被封移除群聊"&#44;"desc":"你已被群主移除群聊"&#44;"preview":"https:\\/\\/downv6.qq.com\\/extendfriend\\/lbsshare_icon.jpg"&#44;"jumpUrl":"https:\\/\\/apis.map.qq.com\\/uri\\/v1\\/geocoder?coord=1.000000&#44;1.000000&amp;referer=macqq&amp;_wv=800"&#44;"tag":"QQ '
                '收藏"&#44;"tagIcon":"https:\\/\\/downv6.qq.com\\/extendfriend\\/collection.png"}}&#44;"config":{"autosize":0&#44;"collect":1&#44;"ctime":1773371998&#44;"forward":1&#44;"height":318&#44;"reply":1&#44;"round":1&#44;"token":"ad9f331ca168748ac3ca3e97a2b41bbf"&#44;"type":"normal"&#44;"width":526}&#44;"text":""&#44;"extraApps":&#91;&#93;&#44;"sourceAd":""&#44;"extra":""}]',
 'font': 14,
 'sub_type': 'normal',
 'message': [{'type': 'json',
              'data': {'data': '{"app":"com.tencent.tuwen.lua","desc":"","view":"news","bizsrc":"favorites.note","ver":"0.0.0.1","prompt":"[QQ收藏] '
                               '位置分享","appID":"","sourceName":"","actionData":"","actionData_A":"","sourceUrl":"","meta":{"news":{"title":"你已被封移除群聊","desc":"你已被群主移除群聊","preview":"https:\\/\\/downv6.qq.com\\/extendfriend\\/lbsshare_icon.jpg","jumpUrl":"https:\\/\\/apis.map.qq.com\\/uri\\/v1\\/geocoder?coord=1.000000,1.000000&referer=macqq&_wv=800","tag":"QQ '      
                               '收藏","tagIcon":"https:\\/\\/downv6.qq.com\\/extendfriend\\/collection.png"}},"config":{"autosize":0,"collect":1,"ctime":1773371998,"forward":1,"height":318,"reply":1,"round":1,"token":"ad9f331ca168748ac3ca3e97a2b41bbf","type":"normal","width":526},"text":"","extraApps":[],"sourceAd":"","extra":""}'}}],
 'message_format': 'array',
 'post_type': 'message',
 'group_id': 2169027872,
 'group_name': '入机窝'}

{'self_id': 168238719,
 'user_id': 2925774824,
 'time': 1773371026,
 'message_id': 1765656926,
 'message_seq': 1765656926,
 'real_id': 1765656926,
 'real_seq': '123754',
 'message_type': 'group',
 'sender': {'user_id': 2925774824,
            'nickname': '星火燃愿(◕ ω＜)ಣ',
            'card': '哈基愿',
            'role': 'member'},
 'raw_message': '[CQ:json,data={ "app": "com.tencent.map"&#44; "config": { '
                '"autoSize": 1&#44; "forward": 1&#44; "height": "60"&#44; '
                '"type": "normal"&#44; "width": "666" }&#44; "desc": ""&#44; '
                '"meta": { "Location.Search": { "address": "你已被群主强奸"&#44; '
                '"enum_relation_type": 1&#44; "from": "plusPanel"&#44; '
                '"from_account": 2147483647&#44; "id": ""&#44; "lat": "1"&#44; '
                '"lng": "1"&#44; "name": "你已被群主强奸"&#44; "uint64_peer_account": '
                '"chaijun" } }&#44; "prompt": "你已被移除群聊"&#44; "ver": '
                '"1.1.2.21"&#44; "view": "LocationShare" }]',
 'font': 14,
 'sub_type': 'normal',
 'message': [{'type': 'json',
              'data': {'data': '{ "app": "com.tencent.map", "config": { '
                               '"autoSize": 1, "forward": 1, "height": "60", '
                               '"type": "normal", "width": "666" }, "desc": '
                               '"", "meta": { "Location.Search": { "address": '
                               '"你已被群主强奸", "enum_relation_type": 1, "from": '
                               '"plusPanel", "from_account": 2147483647, "id": '
                               '"", "lat": "1", "lng": "1", "name": "你已被群主强奸", '
                               '"uint64_peer_account": "chaijun" } }, '
                               '"prompt": "你已被移除群聊", "ver": "1.1.2.21", '
                               '"view": "LocationShare" }'}}],
 'message_format': 'array',
 'post_type': 'message',
 'group_id': 2169027872,
 'group_name': '入机窝'}