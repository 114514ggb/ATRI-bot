import re
from .permissions_management import Permissions_management

class Command(Permissions_management):
    
    def verifyParameter(self, parameter_list, quantity_list):
        """
        验证参数长度。

        :param parameter_list: 参数列表，应包含两个子列表。
        :param quantity_list: 参数数量限制列表，每个元素是一个包含最小值和最大值的元组。
        :return: 验证通过的参数及其长度的两个list。
        """
        (min_appoint, max_appoint), (min_other, max_other) = quantity_list
        
        appointed_params = parameter_list[0]
        other_params = parameter_list[1]
        appointed_length = len(appointed_params)
        other_length = len(other_params)

        if not (min_appoint <= appointed_length <= max_appoint):
            raise ValueError(f"指定参数数量应在{min_appoint}到{max_appoint}之间，实际为{appointed_length}")
        if not (min_other <= other_length <= max_other):
            raise ValueError(f"其他参数数量应在{min_other}到{max_other}之间，实际为{other_length}")
        
        # 如果所有参数都符合要求，则返回参数及其长度
        return [appointed_params, appointed_length], [other_params, other_length]
        
    def processingParameter(self,command):
        """提取参数"""
        pattern_command_argumrnts = r'-([^\s-]+)' #匹配参数'-'开头
        pattern_command_other_argumrnts = r'(?<=\s)([^/\s-]\S*)' #匹配命令其他参数

        command_argumrnts = re.findall(pattern_command_argumrnts, command)
        command_other_argumrnts = re.findall(pattern_command_other_argumrnts, command)

        return [command_argumrnts,command_other_argumrnts]