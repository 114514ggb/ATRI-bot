import random

class Chance():
    def judgeChance(self,chance):
        """根据概率判断是否中奖输入默认百分比概率"""
        random_unmber = random.random()*100
        if chance <= random_unmber:
            return True
        else:
            return False

    def random_Radius(self,a,b):
        """在范围内随机生成int整数,包括a和b"""
        return int(random.uniform(a, b+1))