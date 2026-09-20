
#先把文件config copy.json,supplier_config copy.json重命名成config.json,supplier_config.json再根据注释填写
{
    "platforms": {
        # connection_type 决定用哪个配置, 三种模式:
        #WebSocket_client
        "napcat": {#这个目前只有napcat
            "adapter": "onebot",
            "connection_type": "WebSocket_client",
            "access_token": "ATRI114514",
            "url": "127.0.0.1:8888",       # 连接地址
            "enabled": True,               # 可选,默认 true
            "source_name": ""              # 可选,空=取平台名
        },
        #WebSocket_server
        "napcat_server": {#如果要用这个连接方式记得把napcat_server改成napcat
            "adapter": "onebot",
            "connection_type": "WebSocket_server",
            "access_token": "ATRI114514",
            "host": "0.0.0.0",           # 监听地址
            "port": 8888,                # 监听端口
            "enabled": False,
            "source_name": ""
        },
        #http
        "napcat_http": {#如果要用这个连接方式记得把napcat_http改成napcat
            "adapter": "onebot",
            "connection_type": "http",
            "access_token": "ATRI114514",
            "url": "http://127.0.0.1:8888",
            "host": "127.0.0.1",
            "port": 8888,
            "enabled": False,
            "source_name": ""
        }
    },
    "root_user_id": 2631018780,#root用户的qq号，有执行命令的最高权限，不管在哪个群都会无视其他配置名单强制接受这个qq号的消息
    "account":{
        "id":2430843831, #bot的qq号
        "name":"atri~" #bot的账号名称
    },
    "file_path":{#没事的话可以不配置目录,使用默认的即可,注意如果没有对应目录的话会自动创建
        "resolve_paths": False,#是否强制将相对路径转为绝对路径
        "create_dirs": False,#是否目录创建,确保目录存在
        "document_root": None,#项目的资源根目录，如表情包、音频等目录的配置位置,如果为空就是默认在根目录下的/document文件夹下,有需要的人可以换个位置但是不建议
        "emoji": None,#表情目录的绝对路径,为空的话默认是 项目的根目录/document/img/emojis
        "relative_to_root":{#根目录在main.py脚本的位置会自动获取
            "commands":"atribot/commands", #加载提供系统使用命令的目录
            "chat_manager":"atribot/LLMchat/character_setting", #角色设定所在的目录
            "supplier_config_path":"assets/supplier_config.json", #供应商配置文件路径
            "tool_calls":"atribot/LLMchat/tools",#供ai调用工具实现文件夹
            "mcp_config":"atribot/LLMchat/MCP/mcp_server.json", #MCP 配置文件路径
            "agent_skills":"atribot/LLMchat/skills/agent_skills", #读取skills的目录
            "plugins":"atribot/plugins" #插件目录
        },
        "relative_to_document":{#相对于 document_root 的目录
            "audio":"audio", #音频目录
            "file":"file", #文件目录
            "img":"img", #图片目录
            "video":"video", #视频目录
            "temp":"temp" #临时目录
        },
        "path_mapping": {
            "c:/程序文件/python/ATRI-main": "/mnt/c/程序文件/python/ATRI-main" #路径前缀的映射，bot 和协议端不在同一文件系统时用于转换发送的 `file://` 路径。为空时不做任何转换
        }
    },
    "model":{ 
        "connect":
        {
            "supplier":"zaxprisのapi",#配置的聊天模型来自的供应商(对应 supplier_config.json 中 api[].name)
            "model_name":"Nvidia/deepseek-ai/deepseek-v4-flash",#配置的聊天模型名称(对应 supplier_config.json 中 models 的 key)
            "user_global_context":True #上下文模式: True=群聊每个人独立上下文（使用自己的私聊上下文）, False=每个群的人共享一个群聊上下文
        },
        "chat_parameter":{#聊天模型会使用的参数配置
            "thinking_level":"high",#minimal,low,medium,high
            "temperature":0.3,
            "max_tokens": 8000,
            "response_format":{ "type": "json_object" },#我还挺支持用这个参数的这样效果还行一般不会出现无法解析的格式
            "stream":False,
            "tool_choice": "auto"
        },
        "tavily_search_API_key":"",#一个网络搜索的api挺好用的(免费) https://docs.tavily.com/
        "detection_image":{#用于视觉辅助,给没有视觉的模型提供文字描述使用的模型
            "supplier":"bigModel",
            "model_name":"GLM-4.6V-Flash"
        },
        "detection_audio":{#给没有输入音频能力的模型提供文字描述使用的模型
            "supplier":"",
            "model_name":""
        },
        "detection_video":{#给没有输入视频能力的模型提供文字描述使用的模型
            "supplier":"bigModel",
            "model_name":"GLM-4.6V-Flash"
        },
        "memory":{#总结群聊天内容做为模型记忆的模型
            "summarize_model":{
                "supplier":"zaxprisのapi",
                "model_name":"Nvidia/moonshotai/kimi-k2-instruct-0905"
            }
        },
        "agency_Agent":{#给ai子代理使用的模型
            "supplier":"zaxprisのapi",
            "model_name":"Nvidia/moonshotai/kimi-k2.6"
        },
        "standby_model":[#当主聊天模型尝试失败后会使用的其他供应商或其他的模型,但是备用模型会使用的model参数是一个默认的通用参数硬编码在里面
            {            
                "supplier":"星见雅api",
                "model_name":"z-ai/glm-5.1"
            },            
            {
                "supplier":"zaxprisのapi",
                "model_name":"Nvidia/deepseek-ai/deepseek-v4-pro"
            },
            {
                "supplier":"zaxprisのapi",
                "model_name":"Nvidia/moonshotai/kimi-k2-instruct"
            },
            {
                "supplier":"zaxprisのapi",
                "model_name":"Nvidia/moonshotai/kimi-k2-instruct-0905"
            },
            {
                "supplier":"deepseek",
                "model_name":"deepseek/DeepSeek-V4-Flash"
            },
            {
                "supplier":"bigModel",
                "model_name":"GLM-4.6V-Flash"
            }
        ],
        "RAG":{#对模型提供记忆搜索支持的嵌入式模型
            "enable":True,#这个目前没什么用修不修改不影响,整个项目需要依赖这个
            "dimensions":1024,#这是嵌入模型的向量维度
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
        "playRole":"ATRI_simplify",#聊天采用的人设名要是前面chat_manager里面有的人物，不然就是没有人设
        "ai_max_record":10,#上下文的消息存储的消息轮数
        "group_max_record":20,#群消息缓存的消息条数量为ai上下文的
        "private_max_record":20#user上下文消息轮数限制
    },#注意消息轮数是指你输入一条消息然后等到ai回复一次这就是一轮,这一轮里面可能包含ai多次工具调用什么的
    "sand_box":{#这个是沙盒的的配置参数，需要看具体使用的沙盒实例来传递参数
        #type 沙盒后端类型：
        #  "docker" (默认) Docker容器沙盒，参数见 atribot\LLMchat\sandbox\docker_sandbox.py
        #  "none"  「没有沙盒」，直接在本机执行命令和代码(无任何隔离，注意安全)，支持Linux/Windows
        #          专属参数: "work_dir" 本地工作区根目录(默认 项目根/sandbox_workspace)、
        #                   "shell" 指定shell程序(默认自动: Linux用/bin/sh; Windows优先找Git Bash,找不到退回cmd)
        #          见 atribot\LLMchat\sandbox\no_sandbox.py
        #  "e2b"   E2B云端沙盒，参数见 atribot\LLMchat\sandbox\E2B_sandbox.py
        "type":"docker",
        "image":"atri-sandbox:latest"#启动的镜像名称(docker后端)
    },
    "tool_presets": {#各个聊天模块所使用的工具列表, 每一项对应 LLMchat/tools/ 下的一个工具目录名
        # group_chat / private_chat / agency_Agent 三个模块都支持三种取值:
        # 1) 列表(白名单): 只有列表内的工具会直接暴露给模型; 列表为空代表该模块没有任何工具
        # 2) 字典: {"default": [...], "deferred": [...]} 拆分为"默认启用"与"待发现"两组 (如 group_chat)
        # 3) null: 不限制, 该模块直接使用全部已加载的工具 (不推荐, 很多工具是专有的)
        # 注意: 省略某个模块的键 != null, 省略后该模块等于没有工具(日志有警告), 想用全部工具必须显式写 null
        "group_chat": {#群聊使用的工具
            "default": [#默认直接暴露, 模型可直接调用
                "web_search", "web_extract",
                "memory_search", "memory_storage",
                "load_skill_prompt", "get_user_info",
                "tool_search"#用于发现并临时启用 deferred 中的工具,如果配置了deferred必须要配置这个工具不然发现不了
            ],
            "deferred": [#待发现工具, 不会直接暴露; 模型可通过 tool_search 搜索后在本轮临时启用(仅本轮有效)
                # 注意: tool_search 与 deferred 必须成对出现(WebUI保存时会校验):
                #   配了 deferred 就必须把 tool_search 加进 default, 不然发现不了
                #   default 里有 tool_search 就必须在 deferred 至少放一个工具, 不然没有可发现的内容
                "run_python_code",
                "run_command",
                "send_file","add_file",
                "send_image_message",
                "schedule_self_trigger", "sub_agent"
            ]
        },
        "private_chat": {#私聊使用的工具, 也可以写成普通列表(白名单)
            "default": [
                "web_search", "memory_search",
                "load_skill_prompt", "get_user_info",
                "tool_search"
            ],
            "deferred": [
                "run_python_code",
                "send_file","add_file",
                "send_image_message","send_speech_message",
                "schedule_self_trigger"
            ]
        },
        "agency_Agent": [#子代理(子 agent)使用的工具, 不支持 tool_search 发现机制, 字典格式时只取 default 部分
            "run_command",
            "send_file","add_file",
            "get_user_info", "memory_search",
            "web_search", "web_extract"
        ]
        # 如需某个模块使用全部工具: "模块名": null
        #但是不推荐这么做,很多工具都是专有的
    },
    "group_white_list":[
        2169027872#有效的群白名单
    ],
    "group_initiative_chat_white_list":[#默认的启动主动聊天的名单，首先这个名单出现过的要也在group_white_list出现过，才有效
    ],
    "group_information_extraction":[#默认的启动群消息提取，会由summarize_model配置的模型进行提取然后存入数据库
    ],
    "private_chat_white_list":[#启动私聊的列表
    ],
    "database":
    {
        "host":"127.0.0.1",#数据库连接ip地址
        "port":5432,#连接的端口号
        "user":"postgres",#连接数据库的user名称
        "password":"180710"#密码
    },
    "web_panel":{#Web 管理面板的配置，可选；整个节点不写的话默认启用、端口 5125
        "enable":True,#是否启动管理面板，启动后浏览器访问 http://127.0.0.1:端口/admin/
        "port":5125,#面板监听的端口，只绑定本机 127.0.0.1，外部无法访问
        "access_token":""#面板登录令牌，留空就用第一个平台的 access_token，也可以用环境变量 ATRI_PANEL_TOKEN 指定
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
                "deepseek-chat": {#模型名称(对应上面使用的"model_name")和对应的模型参数
                    #可以输入的多模态类型
                    "visual_sense": False,  #是否支持输入视觉/图像
                    "audio_sense": False,   #是否支持输入音频/语音
                    "video_sense": False,   #是否支持输入视频
                    "document_sense": False  #是否支持输入复杂文档(如PDF解析)
                },
                "deepseek-reasoner": {#可以不写代表默认都不支持
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
