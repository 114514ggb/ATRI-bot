from fastapi import FastAPI
import uvicorn
from atri_head.Message_processing import group_message_processing

app = FastAPI()

base_url = "http://localhost:8080"
token = "ATRI114514"
model = "ATRI"
# model = "gemma2:9b"
# model = "gemma2:27b"
# model = "qwen2.5:32b"

qq_white_list = [1062704755,984466158] # qq群白名单
qq_white_list.append(235984211) #形形色色的群
# qq_white_list.append(946533123) #狗熊岭

ATRI = group_message_processing(base_url, token, model)

@app.post("/")
async def receive_event(data: dict): 
    print("Received event:", data)

    await ATRI.main(data, qq_white_list)

    return "OK", 200

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=3000)