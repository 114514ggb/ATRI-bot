import time

class Chance():
    """提供随机"""
    def __init__(self):
        self.m = 2**32
        self.a = 1664525
        self.c = 1013904223
        # 用当前时间戳（纳秒级）初始化种子
        self.seed = int(time.time_ns() % self.m)
    
    def _next_rand(self):
        """生成[0, m-1]范围内的随机整数并更新种子"""
        self.seed = (self.a * self.seed + self.c) % self.m
        return self.seed
    
    def _random_float(self)->float:
        """生成[0.0, 1.0)范围内的随机浮点数"""
        return self._next_rand() / self.m
    
    def judgeChance(self, chance:int)->bool:
        """根据百分比概率判断是否中奖"""
        random_number = self._random_float() * 100
        
        return random_number < chance
    
    def random_Radius(self, a:int, b:int)->int:
        """在[a, b]范围内生成随机整数（包含端点）"""
        if a > b:
            raise ValueError("范围无效：a 必须小于等于 b")
        range_size = b - a + 1

        return a + self._next_rand() % range_size

    def random_choice(self, seq:list):
        """从非空序列中随机选择一个元素"""
        if not seq:
            raise ValueError("序列不能为空")

        index = self.random_Radius(0, len(seq) - 1)
        return seq[index]