
def distance(s1: str, s2: str) -> int:
    """
    计算两个字符串之间的Levenshtein距离（编辑距离）。
    
    Levenshtein距离是指两个字符串之间，由一个转成另一个所需的最少编辑操作次数。
    允许的编辑操作包括：插入一个字符、删除一个字符、替换一个字符。
    
    Args:
        s1 (str): 第一个字符串
        s2 (str): 第二个字符串
        
    Returns:
        int: 两个字符串之间的编辑距离
        
    Example:
        >>> distance("kitten", "sitting")
        3
        >>> distance("hello", "hallo")
        1
        >>> distance("", "abc")
        3
    """
    ...

def similarity(s1: str, s2: str) -> float:
    """
    计算两个字符串之间的相似度百分比。
    
    相似度基于Levenshtein距离计算：
    similarity = (1 - distance / max_length) * 100
    
    Args:
        s1 (str): 第一个字符串
        s2 (str): 第二个字符串
        
    Returns:
        float: 相似度百分比，范围为0.0-100.0
        
    Example:
        >>> similarity("hello", "hallo")
        80.0
        >>> similarity("abc", "abc")
        100.0
        >>> similarity("", "")
        100.0
    """
    ...