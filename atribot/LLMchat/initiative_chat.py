from atribot.core.types import RichData,TimeWindow




class initiativeChat:
    """决定bot如何在合适的时机加入聊天"""
    
    def __init__(self):
        pass
    
    def decision(self, message:RichData)->bool:
        """决策是否应该发言"""
        pass