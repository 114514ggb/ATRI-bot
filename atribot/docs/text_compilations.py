from pprint import pp


async def db_sql():    
    from atribot.core.db.atri_async_postgresql import atriAsyncPostgreSQL
    from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
    
    http = "http://localhost:11434/api/embed"
    key = "ollama"
    model = "dengcao/Qwen3-Embedding-0.6B:F16"
    
    chat:universal_ai_api = await universal_ai_api.create(base_url = http, api_key = key)
    
    psql_db = await atriAsyncPostgreSQL.create(
      user = "postgres",
      database = "atri"
    )
    
    #存储
    # sql = """
    # INSERT INTO atri_memory 
    #     (group_id, user_id, event_time, event, event_vector) 
    # VALUES 
    #     ($1, $2, $3, $4, $5)
    # """ 
    
    #查询
    # sql = """
    # SELECT 
    #     event
    # FROM atri_memory
    # WHERE event_vector <=> $2::vector(1024) <= 0.7
    # ORDER BY event_vector <=> $1::vector(1024) ASC
    # LIMIT $2
    # """    
    
    sql = """
    SELECT 
        event,
        event_vector <=> $1::vector(1024) as distance
    FROM atri_memory
    WHERE event_vector <=> $1::vector(1024) <= 0.7
    ORDER BY distance ASC
    LIMIT $2
    """
    
    # from atribot.LLMchat.RAG.text_chunker import RecursiveCharacterTextSplitter
    # text_chunker = RecursiveCharacterTextSplitter(200,50)
    
    # with open("E:/程序文件/python/ATRI-main/document/file/atri_my_dear_moments.txt",'r',encoding = 'utf-8') as file:
    #   test_list = text_chunker.split_text(file.read())
    
    
    # async with psql_db as db:
    #   for test in test_sentences:
    #     embedding = await chat.generate_embedding_vector(
    #       model = model,
    #       input = test,
    #       dimensions = 1024
    #     )
    #     await db.execute_with_pool(
    #       sql,
    #       (None,None,int(time.time()), test, str(embedding[0]))
    #     )
    
    async with psql_db as db:
      embedding = await chat.generate_embedding_vector(
        model = model,
        input = "向量数据库常用",
        dimensions = 1024
      )
      ret = await db.execute_with_pool(
        sql,
        (str(embedding[0]),5),
        fetch_type = "all"
      )
      pp(ret)
    
    
    # with open("test.txt",'w',encoding = 'utf-8') as file:
    #   file.write(str(text))
    
    # pp(text)
    
    
async def model_api():
    from atribot.LLMchat.model_api.universal_async_llm_api import universal_ai_api
    
    http = "http://40.83.223.214:3000/v1/chat/completions"
    key = "sk-YL9iOaWSfetLK9LiBfw61bzx2cgt0piBLi0DZ4UfVfOfkM5y"
    model = "google-ai-studio/gemini-2.5-flash"
    # model = "google-ai-studio/gemini-2.5-pro"
    
    tools = [
        {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
            "type": "object",
            "properties": {
                "location": {
                "type": "string",
                "description": "The city and state, e.g. Chicago, IL"
                },
                "unit": {
                "type": "string",
                "enum": ["celsius", "fahrenheit"]
                }
            },
            "required": ["location"]
            }
        }
        }
    ]
    
    messages = [
        # {"role": "user", "content": "还有你看的到你能用的工具吗？你支持函数调用吗？如果支持的话说说有什么工具？没有的话也没关系，这是一条测试消息"}
        # {"role": "user", "content": "9.11和9.8相比哪个数大?"}
        # {"role": "user", "content": "解决 2025 年 AIME 中的问题 1：求出所有整数基数 b > 9 的和，使得 17b 是 97b 的除数"}
        {"role": "user", "content": "你好,你是？你能干什么？"}
        # {
        #     "role": "user",
        #     "content": [
        #         {"type": "image_url","image_url": {"url": "https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhT3LLD3CApCP_s28F4I_MHiVihQNhi6igMg_woo2921tqS1jgMyBHByb2RQgL2jAVoQqGshD06AHqEhnkyMdfschHoC450&rkey=CAESMMAFMZNLna354Uqi8kFvpumaWF--HybIMzG8UiOoZjRUc3Cj48ZpFAG5SFgODvAddA"}},
        #         {"type": "image_url","image_url": {"url": "https://multimedia.nt.qq.com.cn/download?appid=1407&fileid=EhQz_gWh5zCjzBhWWJ-w91zwq5Xz5hjqt3Mg_woo0KjAtaS1jgMyBHByb2RQgL2jAVoQ8jO1lKyxZPobgniiuDi9q3oCeb8&rkey=CAESMMAFM91zwq5Xz5hjqt3Mg_woo0KjAtaS1jgMyBHByb2RQgL2jAVoQ8jO1lKyxZPobgniiuDi9q3oCeb8&rkey=CAESMMAFMZNLna354Uqi8kFvpumaWF--HybIMzG8UiOoZjRUc3Cj48ZpFAG5SFgODvAddA"}},
        #         {"type": "text","text": "这两张图有什么关系？都有些什么？"}
        #     ]  
        # }
    ]
    
    
    chat:universal_ai_api = await universal_ai_api.create(base_url = http, api_key = key)
    text = await chat.request_fetch_primary(messages = messages, model = model, tools = tools)
    
    
    await chat.aclose()
    
    pp(text)