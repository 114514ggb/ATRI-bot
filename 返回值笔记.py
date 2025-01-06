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
'raw_message': '?', # 消息内容
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
            'file': 'file:D:\图片\Noeur喝咖啡.png'
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
                "needShareCallBack":false&#44;
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


{'error': {'message': 'invalid image input', 'type': 'invalid_request_error', 'param': None, 'code': None}}