from fastapi import FastAPI, WebSocket, Depends
from atri_head.Message_processing import group_message_processing
from atri_head.Basics.WebSocketClient import WebSocketClient
from typing import List, Dict, Any
# from functools import cache
import uvicorn
import asyncio
# import threading


http_base_url = "http://localhost:8088" 
ws_url = "127.0.0.1:8080"         
access_token = "ATRI114514"
playRole = "猫娘"  # 默认聊天扮演角色 
connection_type = "WebSocket_client"
Server_port = 3000

qq_white_list: List[int] = [1062704755, 984466158, 1038698883]  # qq群白名单
qq_white_list.append(235984211)  # 形形色色的群
# qq_white_list.append(936819059) #真爱协会
# qq_white_list.append(946533123) #狗熊岭


# @cache
def get_bot():
    """返回 bot 实例"""
    return group_message_processing(
        http_base_url = http_base_url, 
        token = access_token, 
        playRole = playRole, 
        connection_type = connection_type, 
        qq_white_list = qq_white_list
    )

app = FastAPI()

# ---------------------- HTTP 路由 ----------------------
@app.post("/")
async def handle_http_event(data: Dict[str, Any], bot: group_message_processing = Depends(get_bot)):
    """处理HTTP事件"""
    # threading.Thread(target=lambda: asyncio.run(bot.main(data))).start()
    asyncio.create_task(bot.main(data))
    return {"status": "OK", "code": 200}

# ---------------------- WebSocket 路由 ----------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, bot: group_message_processing = Depends(get_bot)):
    """WebSocket连接（服务端模式）"""
    token = websocket.query_params.get("access_token")
    if token != access_token:
        await websocket.close(code=1008)  # 1008 表示权限错误
        return
    
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            await bot.main(data)
            await websocket.send_json({"status": "processed"})
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()



async def run_websocket_server():
    """WebSocket连接客户端"""
    my_client = WebSocketClient(
        uri=ws_url, 
        access_token=access_token
    )
    
    bot = get_bot()#单例问题必须要在WebSocketClient后实例化
     
    await my_client.connect()

    my_client.add_listener(bot.main)
    
    await my_client.start_while()


async def Start_server():
    """根据连接类型启动服务"""
    if connection_type in ["http", "WebSocket_server"]: #作为服务端
        
        config = uvicorn.Config(
            app, 
            host="localhost", 
            port=Server_port,
            workers=8 #进程数
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    elif connection_type == "WebSocket_client": #作为客户端
        await run_websocket_server()
    
    else:
        raise ValueError(f"不支持的连接类型: {connection_type}")



if __name__ == "__main__":
    try:
        asyncio.run(Start_server())
    except KeyboardInterrupt:
        print("服务已停止!")
    except Exception as e:
        print(f"服务运行出错: {e}")
        
        
        
        
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

# _____/\\\\\\\\\____        __/\\\\\\\\\\\\\\\_        ____/\\\\\\\\\_____        __/\\\\\\\\\\\_        
#  ___/\\\\\\\\\\\\\__        _\///////\\\/////__        __/\\\///////\\\___        _\/////\\\///__       
#   __/\\\/////////\\\_        _______\/\\\_______        _\/\\\_____\/\\\___        _____\/\\\_____      
#    _\/\\\_______\/\\\_        _______\/\\\_______        _\/\\\\\\\\\\\/____        _____\/\\\_____     
#     _\/\\\\\\\\\\\\\\\_        _______\/\\\_______        _\/\\\//////\\\____        _____\/\\\_____    
#      _\/\\\/////////\\\_        _______\/\\\_______        _\/\\\____\//\\\___        _____\/\\\_____   
#       _\/\\\_______\/\\\_        _______\/\\\_______        _\/\\\_____\//\\\__        _____\/\\\_____  
#        _\/\\\_______\/\\\_        _______\/\\\_______        _\/\\\______\//\\\_        __/\\\\\\\\\\\_ 
#         _\///________\///__        _______\///________        _\///________\///__        _\///////////__