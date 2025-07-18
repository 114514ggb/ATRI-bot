from typing import Match
# from ..Basics.chance import Chance
import random
import os
import re

class emoji_core:
    """管理表情包"""
    
    def __init__(self,folder_path:str = ""):
        self.emoji_file_dict:dict[str : list[str]] = {}
        """表情目录字典"""
        
        # self.Chance = Chance()
        if folder_path != "":
            self.init_emoji_catalogue(folder_path)
        
        
    def init_emoji_catalogue(self,folder_path:str)->None:
        """
        把指定目录下的表情文件索引写入表情目录字典
        """
        if not os.path.exists(folder_path):
            raise ValueError(f"表情文件夹路径不存在: {folder_path}")
        
        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)
            if os.path.isdir(item_path):
                files = [f for f in os.listdir(item_path) 
                         if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]
                if files:
                    self.emoji_file_dict[item] = files
                    
        print("\n成功建立表情索引!")
        
    
    def extract_emotion_tags(self, text: str) -> list:
        """从文本中提取标签"""
        tags = []
        start = 0
        while True:
            start = text.find('<', start)
            if start == -1:
                break
            end = text.find('>', start)
            if end == -1:
                break
            tag = text[start+1:end].lower()
            if tag in self.emoji_file_dict:
                tags.append(tag)
            start = end + 1
        return tags
    
    
    def remove_emotion_tags(self, text: str)-> str:
        """把字符串除去记录在内的表情标签"""
        
        def replace_if_valid(match:Match[str]) -> str:
            tag = match.group(1)
            return '' if tag in self.emoji_file_dict else match.group(0)
        
        return re.sub(r'\[(.*?)\]', replace_if_valid, text)


    def get_random_emoji_name(self, tag:str)->str:
        """根据所属标签随机返回一个文件名"""
        # return self.Chance.random_choice(self.emoji_file_dict[tag]) if tag in self.emoji_file_dict else None
        return random.choice(self.emoji_file_dict[tag]) if tag in self.emoji_file_dict else None
    
    
    
    def process_text_and_emotion_tags(text: str, emoji_dict: dict) -> tuple[str, list[str]]:
        """
        过滤字符串标签并且提取标签
        
        Args:
            text: 要处理的字符串
            emoji_dict: 指定的标签字典

        Returns:
            tuple[str, list[str]]: 处理过的字符串和标签组成的元组
        """
        tags_list = []
        result_chars = []
        i = 0
        number = len(text)
        
        while i < number:
            char = text[i]
            if char == '<':
                start = i + 1  # 记录标签开始位置
                i += 1

                while i < number and text[i] != '>':
                    i += 1
                if i < number:
                    tag_content = text[start:i]
                    if tag_content in emoji_dict:
                        tags_list.append(tag_content)
                        i += 1
                        continue  # 跳过添加标签内容到结果

                    i = start - 1

            result_chars.append(char)
            i += 1
        
        return (''.join(result_chars), tags_list)
    
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """计算两个字符串的编辑距离

        Args:
            s1: 第一个字符串
            s2: 第二个字符串

        Returns:
            int: 编辑距离
        """
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]


class emoji_record:
    """表情数据容器"""
    pass
    
if __name__ == "__main__":
    pass
    # ec = emoji_core()
    # ec.init_emoji_catalogue("E:/程序文件/python/ATRI/document/img/emojis")
    # print(emoji_core.process_text_and_emotion_tags("[happy]qweqweqewqe",ec.emoji_file_dict))
    # print(ec.emoji_file_dict)
    # for _ in range(1,10):
    #     print(ec.get_random_emoji_name("happy"))
    # print(ec._levenshtein_distance("检查目录是否为空","啊啊啊")) 
