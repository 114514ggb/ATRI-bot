from .simple_commands import *
import multiprocessing
import asyncio
import os

class command_processor():
    """指令处理器"""
    # "/manage""/管理"添加管理员权限或黑名单
    command_list = {
        "/help":"1001","/帮助":"1001",
        "/kill":"1002","/清除上下文":"1002",
        "/fortune":"1003","/今日运势":"1003",
        "/img":"1004","/图片":"1004",
        "/test":"3005",#测试指令
        "/Permissions":"0006","/查看权限":"0006",
        "/sing":"3007","/唱歌":"3007",
        "/toggle":"3008","/切换模型":"3008",
        "/voice":"1009","/说话":"1009",
        # "/MD5":"1010","/加密":"1010",
    }
    """命令列表，格式为{命令:命令编号}，命令编号第一位是权限等级，后三位是命令编号一般是按照注册顺序来的"""
    
    def_list ={
        "1001":help,
        "1002":kill,
        # "1003":Random_fortune,
        "1004":random_img,
        "3005":test,
        "0006":permissions_my,
        "3007":sing,
        "3008":toggleModel,
        "1009":audio,
        # "1010":encryptedMessage,
    }
    """命令列表，格式为{命令编号:函数}"""

    async def main(self, user_input, qq_id, data):
        """主函数,创建进程执行指令"""
        process = multiprocessing.Process(
            target=self.subroutine, 
            args=(user_input, qq_id, data),
            name="command_processing"
        )
        process.start()
        
        return "ok"
    
    def subroutine(self, *args, **kwargs):
        """子函数,创建进程执行指令"""
        asyncio.run(self.command_processing(*args, **kwargs))

    async def command_processing(self,user_input,qq_id,data):
        """处理执行用户输入指令"""
        try:
            def_id ,command = basics.Command.receive_command(user_input, data['user_id'], self.command_list)

            try:
                if def_id in self.def_list:

                    await self.def_list[def_id](user_input=user_input, qq_TestGroup=qq_id, data=data)
                    print(f"ATRI:指令:{command},执行成功!")
                    return "ok"

                else:
                    raise Exception("该指令已经注册,但是没有实现")

            except Exception as e:
                await basics.QQ_send_message.send_group_message(qq_id,"执行指令出错了，请稍后再试!😰\nType Error:"+str(e))
                return "no"

        except Exception as e:
            await basics.QQ_send_message.send_group_message(qq_id,"ATRI用手挠了挠脑袋,表示不理解这个指令😕\nType Error:"+str(e))
            return "no"

    def Load_additional_commands(self):
        """加载额外指令"""
        
        folder_path = "atri_head\ImplementationCommand\plugins"
        finally_key = int(list(self.def_list.keys())[-1][-3:])

        # print("正在加载插件...")
        for dirpath, __, filenames in os.walk(folder_path):
            if dirpath == folder_path:
                for Class in filenames:
                    if Class.endswith(".py") and Class != "example_plugin.py":

                        finally_key += 1
                        dirname = Class[:-3]
                        namespace = {'finally_key': finally_key, 'dirname': dirname, "def_list": self.def_list}
                        # print("加载插件文件：" + dirname)
                        exec("from .plugins." + dirname + " import "+ dirname,globals(),namespace)
                        exec("plugin ="+dirname+"()",globals(),namespace)
                        exec("Command_id = str(plugin.authority_level) + str(finally_key).rjust(3, '0')",globals(),namespace)
                        exec("register_order = plugin.register_order",globals(),namespace)

                        register_order = namespace['register_order']
                        Command_id = namespace['Command_id']

                        for order in register_order:
                            self.command_list[order] = Command_id
                        
                        exec("def_list[Command_id] = plugin."+dirname,globals(),namespace)
        # print("插件加载完成！")
        # print("已注册指令列表："+str(self.command_list))
        return "ok"