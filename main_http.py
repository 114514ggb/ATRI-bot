from fastapi import FastAPI
import uvicorn,asyncio,threading
from atri_head.Message_processing import group_message_processing


app = FastAPI()


http_base_url = "http://localhost:8088"
token = "ATRI114514"
playRole = "ATRI"
# model = "gemma2:9b"
# model = "gemma2:27b"
# model = "qwen2.5:32b"

qq_white_list = [1062704755,984466158] # qq群白名单
qq_white_list.append(235984211) #形形色色的群
# qq_white_list.append(946533123) #狗熊岭
# qq_white_list.append(936819059) #真爱协会


ATRI = group_message_processing(http_base_url=http_base_url, token=token, playRole=playRole, connection_type="http", qq_white_list = qq_white_list)


def run_atrib_main(data, qq_white_list):
    asyncio.run(ATRI.main(data))


@app.post("/")
async def receive_event(data: dict): 
    # print("Received event:", data)

    threading.Thread(target=run_atrib_main, args=(data, qq_white_list)).start()

    return "OK", 200

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=3000)

#                _ooOoo_               
#               o8888888o              
#               88" . "88              
#               (| -_- |)              
#               O\  =  /O              
#            ____/`---'\____           
#          .'  \\|     |//  `.         
#         /  \\|||  :  |||//  \        
#        /  _||||| -:- |||||-  \       
#        |   | \\\  -  /// |   |       
#        | \_|  ''\---/''  |   |       
#        \  .-\__  `-`  ___/-. /       
#      ___`. .'  /--.--\  `. . __      
#   ."" '<  `.___\_<|>_/___.'  >'"".   
#  | | :  `- \`.;`\ _ /`;.`/ - ` : | | 
#  \  \ `-.   \_ __\ /__ _/   .-` /  / 
# ==`-.____`-.___\_____/___.-`____.-'==
#                `=---='               
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#         佛祖保佑        永无BUG