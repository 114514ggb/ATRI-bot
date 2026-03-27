
#先把文件config copy.json,supplier_config copy.json重名成onfig.json,supplier_config.json再根据注释填写
{
    "network":
    {
        "connection_type":"WebSocket_server", #和napcat的连接类型支持连接类型有["http","WebSocket_client","WebSocket_server"]注意http废弃很久了没测试不一定能用
        "access_token":"ATRI114514", #和napcat连接要的验证token
        "url":"127.0.0.1:8888", #连接端口在WebSocket_client和http的时候需要
        "host":"127.0.0.1", #作为服务端的时候开的端口
        "server_port":8888, #作为服务端的时候开的端口号
        "admin_port":1314#Web管理面板
    },
    "root_user_id": 114514,#root用户的qq号，有执行命令的最高权限，不管在哪个群都会无视其他配置名单强制接受这个qq号的消息
    "account":{
        "id":3930909243, #bot的qq号
        "name":"ATRI-bot" #bot的账号名称
    },
    "file_path":{#没事的话可以不配置目录,使用默认的即可,注意如果没有对应目录的话会自动创建
        "document_root":None, #项目的资源根目录，如表情包、音频等目录的配置位置,如果为空就是默认在根目录下的/document文件夹下,有需要的人可以换个位置但是不建议
        "relative_to_root":{#根目录在main.py脚本的位置会自动获取
            "commands":"atribot/commands", #加载提供系统使用命令的目录
            "chat_manager":"atribot/LLMchat/character_setting", #角色设定所在的目录
            "supplier_config_path":"assets/supplier_config.json", #供应商配置文件路径
            "tool_calls":"atribot/LLMchat/tools",#供ai调用工具实现文件夹
            "mcp_config":"atribot/LLMchat/MCP/mcp_server.json", #MCP 配置文件路径
            "agent_skills":"atribot/LLMchat/skills/agent_skills" #读取skills的目录
        },
        "relative_to_document":{#相对于 document_root 的目录
            "emoji":"img/emojis", #表情包目录
            "audio":"audio", #音频目录
            "file":"file", #文件目录
            "img":"img", #图片目录
            "video":"video", #视频目录
            "temp":"temp" #临时目录
        }
    },
    "model":{ 
        "connect":
        {
            "supplier":"deepseek",#配置的聊天模型来自的供应商
            "model_name":"deepseek-chat",#配置的聊天模型名称
            "visual_sense":False,#模型是否有视觉，是否能接收图片
            "user_global_context":True #决定了上下文的存在在形式,是一个群共用一个上下文，还是每个user单独的上下文
        },
        "chat_parameter":{#聊天模型会使用的参数配置
            "thinking_level":"high",#minimal,low,medium,high
            "temperature":0.3,
            "max_tokens": 8000,
            "stream":False,
            "tool_choice": "auto"
        },
        "tavily_search_API_key":"",#一个网络搜索的api挺好用的(免费) https://docs.tavily.com/
        "detection_image":{#用于视觉辅助,给没有的视觉的模型提供文字描述使用的模型
            "supplier":"bigModel",
            "model_name":"GLM-4.1V-Thinking-Flash"
        },
        "memory":{#总结群聊天内容做为模型记忆的模型
            "summarize_model":{
                "supplier":"zaxprisのapi",
                "model_name":"GeminiCLI/gemini-2.5-flash-search",
                "visual_sense":True
            }
        },
        "standby_model":[#当主聊天模型尝试失败后会使用的其他供应商或其他的模型,但是备用模型会使用的model参数是一个默认的通用参数硬编码在里面
            {
                "supplier":"zaxprisのapi",
                "model_name":"GeminiCLI/gemini-2.5-flash-search"
            },
            {
                "supplier":"zaxprisのapi",
                "model_name":"GeminiCLI/gemini-2.5-pro-nothinking"
            },
            {
                "supplier":"zaxprisのapi",
                "model_name":"Nvidia/moonshotai/kimi-k2-instruct-0905"
            },
            {
                "supplier":"kourichat",
                "model_name":"gpt-5-chat-latest"
            },
            {
                "supplier":"deepseek",
                "model_name":"deepseek-chat"
            },
            {
                "supplier":"bigModel",
                "model_name":"GLM-4.6-Flash"
            }
        ],
        "RAG":{#对模型提供记忆搜索支持的嵌入式模型
            "enable":True,
            "dimensions":1024,#嵌入模型的维度,这个目前配置了也没用，有些地方硬编码了没改
            "use_embedding_model":{#一般配置这个就行了
                "supplier":"ollama_embed",
                "model_name":"dengcao/Qwen3-Embedding-0.6B:F16"
            },
            "use_reranker_model":{#下面的配置目前没用
                "supplier":"ollama_embed",
                "model_name":"dengcao/Qwen3-Reranker-8B:Q4_K_M"
            },
            "vector_database":{

            }
        }
    },
    "ai_chat":{
        "playRole":"ATRI",#聊天采用的人设名要是前面chat_manager里面有的人物，不然就是没有人设
        "ai_max_record":20,#上下文的消息存储的消息轮数
        "group_max_record":20,#群消息缓存的消息条数量为ai上下文的
        "private_max_record":20#user上下文消息轮数限制
    },#注意消息轮数是指你输入一条消息然后等到ai回复一次这就是一轮,这一轮里面可能包含ai多次工具调用什么的
    "sand_box":{#这个是沙盒的的配置参数，需要看具体使用的沙盒实例来传递参数,默认使用的是docker，可以去atribot\LLMchat\sandbox\docker_sandbox.py看看class接受的参数
        "image":"atri-sandbox:latest"#启动的镜像名称
    },
    "tool_presets": {#各个聊天模块所使用的工具列表,可以配置列表是空代表没有工具,配置为空值代表使用全部工具
        "chat_full": [
            "web_search", "web_extract",
            "memory_search", "memory_storage",
            "run_python_code",
            "send_image_message", "send_speech_message",
            "load_skill_prompt", "get_user_info",
            "schedule_self_trigger"
        ],
        "chat_lite": [
            "web_search", "memory_search",
            "load_skill_prompt", "get_user_info"
        ],
        "tool_only": [
            "run_python_code", "web_search", "web_extract"
        ],
        "使用全部工具": None
    },
    "group_white_list":[
        984466158#有效的群白名单
    ],
    "group_initiative_chat_white_list":[#默认的启动主动聊天的名单，首先这个名单出现过的要也在group_white_list出现过，才有效
    ],
    "group_information_extraction":[#默认的启动群消息提取，会由summarize_model配置的模型进行提取然后存入数据库
    ],
    "database":
    {
        "host":"127.0.0.1",#数据库连接ip地址
        "port":5432,#连接的端口号
        "user":"postgres",#连接数据库的user名称
        "password":"atri"#密码
    }
}


#下面就是对supplier_config.json配置的注释
{
    "api":[
        {
            "name":"deepseek",#作为上面supplier参考的名称
            "base_url":"https://api.deepseek.com/chat/completions",#只接受有openai兼容的地址
            #一般要在地址后面加上 v1/chat/completions
            #比如谷歌的openai兼容地址https://generativelanguage.googleapis.com/v1beta/openai
            #要加后才能用https://generativelanguage.googleapis.com/v1beta/openai/v1/chat/completions
            #对于嵌入模型就一般不需要了比如这个https://api.siliconflow.cn/v1/embeddings
            #如果有的api文档里有写的话使用curl里面的url地址
            "api_key":"sk-????",#你的密匙这个可以是一个list类型，那样的话就可以输入多个密匙成为一个号池
            "models":{
                "deepseek-chat": {#模型名称(对应上面使用的"model_name")和对应的模型参数，参数目前就一个有没有视觉
                    "visual_sense": False #模型是否有视觉，是否能接收图片
                },
                "deepseek-reasoner": {
                    "visual_sense": False
                }
            }
        },
        {
            "name":"bigModel",
            "base_url":"https://open.bigmodel.cn/api/paas/v4/chat/completions",
            "api_key":"???",#https://open.bigmodel.cn/ (免费)质谱模型的api_key用于视觉辅助没有的视觉的模型提供文字描述
            "models":{
                "GLM-4.7-Flash": {
                    "visual_sense": False
                },
                "GLM-4.6V-Flash": {
                    "visual_sense": True
                },
                "GLM-4-Flash-250414": {
                    "visual_sense": True
                },
                "GLM-4.1V-Thinking-Flash": {
                    "visual_sense": True
                }
            }
        },
        {
            "name":"google",
            "base_url":"https:???",
            "api_key":[
                "AIzaSyDsd4zsgSzI33nfv7DKy1uo-bHpJEaYAP0",#像这样可以配置一个号池，请求时会按照顺序轮流使用里面的key
                "AIzaSyAIlKkjK_nTDQfP84jIDqBmf51mF3e1gws",
                "AIzaSyDdWvgr38Kl28UqmdPfD_8KapB4KHtdEwA",
                "AIzaSyCF9hJhH3dn9Q_-SSjorkJPlsSB0Y6dzMw",
                "AIzaSyCczwFSbyNt8tSyzN1suCgzl9l7urIjT9k",
                "AIzaSyCLbAR5drM-VRzrTFErA0XWrmlPHXFnHY4",
                "AIzaSyDWgpOO2eSv7Jwo_9S-ifeP6Xi23hVIqS8",
                "AIzaSyBdStUPjfcAODSiI1wHCMW-6P_sLS52p5o",
                "AIzaSyAjJZTWz5QGbGEkIXmsJR_gHR89iBjMbDw",
                "AIzaSyDxIEbCfbpr5k6D-4jMklOCU06IkWXPL08"
            ],
            "models":{
                "gemini-2.5-flash": {
                    "visual_sense": True
                },
                "gemini-2.5-pro": {
                    "visual_sense": True
                },
                "gemini-3-flash-preview": {
                    "visual_sense": True
                },
                "gemini-2.5-flash-image-preview": {
                    "visual_sense": True
                }
            }
        },
    ]
}
