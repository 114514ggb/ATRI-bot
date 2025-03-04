from pprint import pprint
from atri_head.ai_chat.async_open_ai_api import async_openAI
from collections import deque
import asyncio
import json
# max_length = 20
# api_key="5f4cbc0d0eaf4cf79422e7109056fd3d.20R5i62X5nQbFqWC"
# url = "https://open.bigmodel.cn/api/paas/v4"

# zhipu_ai = async_openAI(api_key = api_key,base_url = url)

# messages = deque(maxlen=max_length)
# messages.append({"role": "user", "content": "你是？"})

# model = "GLM-4-Flash"

# reply = asyncio.run(zhipu_ai.generate_text(model,messages))
# pprint(reply)
# pprint(messages)
# import requests

# url = "https://api.deepseek.com/models"

# payload={}
# headers = {
#   'Accept': 'application/json',
#   'Authorization': 'Bearer sk-8403066c2841461491dd0b642a6c44af'
# }

# response = requests.request("GET", url, headers=headers, data=payload)

# print(response.text)
