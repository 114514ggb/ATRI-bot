import re
from .permissions_management import Permissions_management

class Command(Permissions_management):
    
    def receive_command(self, command, people, command_list):
        """命令处理,用来判断命令是否存在，是否具有权限,并返回布尔类型或命令编号和命令"""

        pattern_command = r'^\s(/\S+)' #只匹配开头命令

        if "/" in command:

            if my_command := re.findall(pattern_command, command):

                my_command = my_command[0]

                if my_command in command_list:

                    if self.permissions(people, command_list[my_command][0]):

                        return command_list[my_command],my_command
                    
                    else:
                        raise Exception("权限不足")
                else:
                    raise Exception("命令不存在") 
            else:
                raise Exception("格式错误")
        else:
            raise Exception("不是命令")
    
    def verifyParameter(self,Parameter_list,parameter_quantity_min_1 = 0, parameter_quantity_max_1 = 0, parameter_quantity_min_2 = 0, parameter_quantity_max_2 = 0):
        """验证参数长度"""
        parameter_appoint = Parameter_list[0]
        parameter_other = Parameter_list[1]
        parameter_appoint_length = len(parameter_appoint)
        parameter_other_length = len(parameter_other)

        if parameter_quantity_min_1 <= parameter_appoint_length <= parameter_quantity_max_1 and parameter_quantity_min_2 <= parameter_other_length <= parameter_quantity_max_2:
            return parameter_appoint,parameter_appoint_length,parameter_other,parameter_other_length
        else:
            raise Exception("参数数量错误")
        
    def processingParameter(self,command):
        """处理参数"""
        pattern_command_argumrnts = r'-([^\s-]+)' #匹配参数'-'开头
        pattern_command_other_argumrnts = r'(?<=\s)([^/\s-]\S*)' #匹配命令其他参数

        command_argumrnts = re.findall(pattern_command_argumrnts, command)
        command_other_argumrnts = re.findall(pattern_command_other_argumrnts, command)

        return [command_argumrnts,command_other_argumrnts]