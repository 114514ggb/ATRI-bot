from atri_head.Message_processing import group_message_processing
from atri_head.Basics.WebSocketClient import WebSocketClient
import asyncio,threading

playRole = "ATRI"
access_token = "ATRI114514"
ws_url = "127.0.0.1:8080"
# ping_interval = 300

qq_white_list = [1062704755,984466158] # qq群白名单
qq_white_list.append(235984211) #形形色色的群
# qq_white_list.append(946533123) #狗熊岭
# qq_white_list.append(936819059) #真爱协会

async def client():
    my_client = WebSocketClient(uri = ws_url, access_token = access_token)
    ATRI = group_message_processing(playRole = playRole, connection_type = "WebSocket", qq_white_list = qq_white_list)

    while True:
        await my_client.connect()

        my_client.add_listener(ATRI.main)

        await my_client.start_while()

        # def run_atrib_main(data, qq_white_list):
        #     asyncio.run(ATRI.main(data, qq_white_list))

        # print("连接成功!")
        # while True:
        #     data = await websocket.recv()
        #     data = json.loads(data)
            # print("Received event:", data)

            # threading.Thread(target=run_atrib_main, args=(data, qq_white_list)).start()



if __name__ == '__main__':
    asyncio.run(client())