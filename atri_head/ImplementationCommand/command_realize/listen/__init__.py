from atri_head.Basics import Basics,Command_information
# from pypinyin import pinyin, Style
# import jieba
import asyncio
import random
import os

class want_to_listen:
    
    folder_path = "document/audio/ATRI_游戏原音"
    """音频文件夹路径"""
    
    def __init__(self):
        self.basics = Basics()
        self.audio: list = self.load_audio()
        
    def load_audio(self) -> list:
        """读取音频文件"""
        if not os.path.exists(self.folder_path):
            return []
        return [f for f in os.listdir(self.folder_path) if f.endswith(('.mp3', '.wav', '.ogg'))]
    
    async def main(self, argument, group_ID, data):
        """
        返回最匹配文本的一句语音\n
        没有参数的话随机返回
        """
        text = argument[1][0] if len(argument[1]) > 0 else None
        
        if not self.audio:
            raise ValueError("目录下没有音频文件")
        
        if text:
            name = await asyncio.to_thread(self.find_best_match, text)#开一个线程
        else:
            name = random.choice(self.audio)
        
        await self.basics.QQ_send_message.send_group_audio(
            group_ID,
            url_audio="ATRI_游戏原音/" + name,
            default=True
        )
        return "ok"
    
    
    def find_best_match(self, text: str) -> str:
        """根据文本找到最匹配的文件名"""

        matches = []
        for filename in self.audio:
            match_score = self.calculate_match_score(filename, text)
            matches.append((filename, match_score))

        max_score = max(match[1] for match in matches)
        best_matches = [match[0] for match in matches if match[1] == max_score]

        return random.choice(best_matches)
    
    def calculate_match_score(self, filename: str, text: str) -> float:
        """计算文件名与文本的匹配度"""
        
        def levenshtein_distance(s1, s2):
            """编辑距离"""
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
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

        # def jaccard_similarity(s1, s2):
        #     """Jaccard 相似度"""
        #     set1 = set(jieba.lcut(s1))
        #     set2 = set(jieba.lcut(s2))
        #     intersection = set1.intersection(set2)
        #     union = set1.union(set2)
        #     return len(intersection) / len(union) if union else 0

        # def pinyin_similarity(s1, s2):
        #     """拼音匹配"""
        #     pinyin1 = ''.join([item[0] for item in pinyin(s1, style=Style.NORMAL)])
        #     pinyin2 = ''.join([item[0] for item in pinyin(s2, style=Style.NORMAL)])
        #     return 1 - levenshtein_distance(pinyin1, pinyin2) / max(len(pinyin1), len(pinyin2))

        distance_score = 1 - levenshtein_distance(filename, text) / max(len(filename), len(text))
        # jaccard_score = jaccard_similarity(filename, text)
        # pinyin_score = pinyin_similarity(filename, text)

        # return 0.4 * distance_score + 0.3 * jaccard_score + 0.3 * pinyin_score
        return distance_score


listen = want_to_listen()

command_main = Command_information(
    name="listen",
    aliases=["想听", "listen"],
    handler=listen.main,
    description="返回最匹配文本的一句游戏原音,没有参数的话随机返回",
    parameter=[[0, 0], [0, 1]]
)
