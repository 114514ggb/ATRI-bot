from ..Basics import Basics,Command_information
import importlib.util
import os
import re

class command_processor():
    """指令处理器"""
    def __init__(self):
        self.basics = Basics()
        self.command_list:list[Command_information] = [
            Command_information(
                name="help",
                aliases=["帮助", "help"],
                handler= self.helper,
                description="查看帮助",
                authority_level=0,
                parameter=[[0, 1], [0, 1]]
            ),
        ]
        """命令列表"""
        print("初始化指令处理器\n正在加载指令...")
        self.command_load()
        print("指令加载完成!\n")

    async def main(self, user_input: str, qq_id: int, data: dict) -> bool:
        try:
            command, parameter = self.verify_command(user_input, data['user_id'])

            try:
                await command(parameter, qq_id, data) #执行指令
                return True

            except Exception as e:
                await self.basics.QQ_send_message.send_group_message(qq_id,"指令执行异常，请稍后再试!😰\nType Error:"+str(e))
                

        except Exception as e:
            await self.basics.QQ_send_message.send_group_message(qq_id,"ATRI用手挠了挠脑袋,表示不理解这个指令😕\nType Error:"+str(e))
            
        return False

    def verify_command(self, user_input: str, user_qq_id: int):
        """验证指令,用来判断命令是否存在，是否具有权限,参数数量是否正确,成功后返回命令主函数和提取的参数列表"""
        
        pattern_command = r'^\s*/(\S+)'

        if my_command := re.findall(pattern_command, user_input):

            my_command = my_command[0]

            for command in self.command_list:
                if my_command in command.aliases:
                    if self.basics.Command.permissions(user_qq_id, command.authority_level):
                        
                        parameter = self.basics.Command.processingParameter(user_input)
                        self.basics.Command.verifyParameter(parameter,command.parameter)
                        
                        return command.handler,parameter
                    
                    else:
                        raise Exception("权限不足")

            raise Exception("命令不存在")
        else:
            raise Exception("格式错误")

    def command_load(self):
        """加载命令到command_list"""
        folder_path = "atri_head\\ImplementationCommand\\command_realize"
        default_module_name = "command_main"
        
        for name in os.listdir(folder_path):
            dir_path = os.path.join(folder_path, name)
            if os.path.isdir(dir_path):

                file_path = os.path.join(dir_path, "__init__.py")
                if not os.path.exists(file_path):
                    print(f"文件夹{dir_path}中没有__init__.py文件")
                    continue 

                spec = importlib.util.spec_from_file_location(name, file_path)
                
                if spec is None:
                    print(f"导入模块{file_path} 失败！")
                    continue

                module = importlib.util.module_from_spec(spec)

                if module is None:
                    print(f"获取模块{file_path}中的loader 失败！")
                    continue

                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    print(f"加载模块时发生错误：{e}")
                    continue

                func = getattr(module, default_module_name, None)
                if func is None:
                    print(f"获取模块{file_path}中的主处理函数失败！")
                    continue
                
                self.command_list.append(func)
    
    async def helper(self,parameter, qq_id, data):
        """帮助指令"""

        help_text = (
            "GNU atri，版本 1.14.0.96(1)-release (x86_64-pe-Lwinux-gnu)\n"
            "这些 atri 命令是内部定义的。输入 \"/help\" 以获取本列表。\n"
            "输入 \"/help 名称\" 以得到有关函数 \"名称\" 的更多信息。\n"
            "使用 \"/help atri\" 来获得关于 ATRI 的更多一般性信息。\n"
            "使用 \"/help -all\" 或 \"/help -fuck\" 来获取不在本列表中的命令的更多信息\n\n"
            "warn :所有命令以开头要@bot再接一个\"/\"才能使用\n\n"
            "/manage -[controls] [list] [be_operated_qq_id] -管理指令\n"
            "/kill -清除记忆\n"
            "/test -[at_will] [at_will] -测试用命令\n"
            "/role [role_name] -切换聊天角色\n"
            "/permissions -查看自己当前权限"
            "/ls [list_name] -查看系统列表"
        )
        if parameter == [[],[]]:
            await self.basics.QQ_send_message.send_group_message(qq_id,help_text)
        elif parameter == [["all",],[]] or parameter == [["fuck",],[]]:
            
            list_text = "当前可用的命令:\n"
            for command in self.command_list:
                list_text += f"{command.name} : {command.description}\n\n"
            await self.basics.QQ_send_message.send_group_merge_forward(
                qq_id,
                list_text,
                source="指令列表"
            )
            return True
            
        elif parameter == [[],["atri"]]:
            
            introduce = (
                "ATRI 是一个 高性能的 信息处理系统，\n"
                "主要是面对无界的格式化数据流进行处理。\n"
                "简单来说是用于处理对你们在qq发送消息的一个机器人.\n"
                "基本功能:\n"
                "1.@机器人后接文字就可以聊天\n"
                "2.@机器人后接/[命令]即可触发命令.\n"
                "3.会对群出现的一些词进行反应。\n"
                "4.会对交互数据进行存储，可能会对其用于分析，服务质量优化和功能迭代。\n"
                "5.仅为工具型机器人，不具备情感交互能力。建议用户：\n"
                "    - 避免过度依赖AI回复处理现实问题或情绪困扰。\n"
                "    - 如感到心理不适，请及时寻求专业心理咨询服务。\n"
                "    - 如遇心理困扰，请寻求专业帮助（全国心理援助热线：12355）。"
            )
            await self.basics.QQ_send_message.send_group_message(qq_id,introduce)
            return True
        
        elif parameter[0] == [] and len(parameter[1]) == 1:
            
            for command in self.command_list:
                if command.name == parameter[1][0]:
                    command_text = (
                        f"✨<{command.name}>指令信息✨\n"
                        f"├─ 📛 指令名称: {command.name}\n"
                        f"├─ 🏷️ 调用名: {', '.join(command.aliases) if isinstance(command.aliases, (list, tuple)) else command.aliases}\n"
                        f"├─ 📝 功能描述: {command.description}\n"
                        f"├─ 🔐 执行权限: 最低 {command.authority_level} 级\n"
                        f"└─ 🎯 参数要求: {command.parameter}\n"
                    )                 
                    await self.basics.QQ_send_message.send_group_message(qq_id,command_text)
                    return True
            
            raise ValueError("该命令不存在")
                
        else:
            raise ValueError(f"不支持的参数:{parameter}")


