import numpy as np


def levenshtein_distance(s1: str, s2: str) -> int:
    """计算两个字符串之间的Levenshtein编辑距离
    
    使用空间优化的动态规划算法，计算将字符串s1转换为s2所需的最少
    单字符编辑操作次数（插入、删除、替换）。

    Args:
        s1 (str): 第一个字符串
        s2 (str): 第二个字符串

    Returns:
        int: 两个字符串之间的编辑距离
    """
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    if len(s2) == 0:
        return len(s1)

    previous_row = np.arange(len(s2) + 1)

    for i, c1 in enumerate(s1):
        current_row = np.zeros(len(s2) + 1, dtype=int)
        current_row[0] = i + 1

        for j, c2 in enumerate(s2):
            cost = min(
                previous_row[j + 1] + 1,
                current_row[j] + 1,
                previous_row[j] + (1 if c1 != c2 else 0),
            )
            current_row[j + 1] = cost

        previous_row = current_row

    return int(previous_row[-1])


def jaro_winkler_similarity(s1: str, s2: str, p: float = 0.1) -> float:
    """
    计算两个字符串之间的 Jaro-Winkler 相似度 (0.0 到 1.0)。
    
    Args:
        s1 (str): 第一个字符串。
        s2 (str): 第二个字符串。
        p (float): Winkler 调整中的前缀缩放因子，通常为 0.1。

    Returns:
        float: 介于 0.0 和 1.0 之间的 Jaro-Winkler 相似度分数。
    """
    if len(s1) > len(s2):
        s1, s2 = s2, s1

    len1, len2 = len(s1), len(s2)
    if len1 == 0:
        return 0.0

    match_distance = (len2 // 2) - 1
    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches_count = 0
    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)

        for j in range(start, end):
            if s1[i] == s2[j] and not s2_matches[j]:
                s1_matches[i] = True
                s2_matches[j] = True
                matches_count += 1
                break

    if matches_count == 0:
        return 0.0

    transpositions = 0
    cursor = 0
    for i in range(len1):
        if s1_matches[i]:
            while not s2_matches[cursor]:
                cursor += 1
            if s1[i] != s2[cursor]:
                transpositions += 1
            cursor += 1

    jaro_sim = (
        matches_count / len1
        + matches_count / len2
        + (matches_count - transpositions // 2) / matches_count
    ) / 3.0

    common_prefix_len = 0
    for i in range(min(len1, 4)):
        if s1[i] == s2[i]:
            common_prefix_len += 1
        else:
            break

    if common_prefix_len == 0:
        return jaro_sim
    return jaro_sim + common_prefix_len * p * (1 - jaro_sim)


def calculate_similarity(embedding1: list[float], embedding2: list[float]) -> float:
    """计算两个向量之间的余弦相似度。

    余弦相似度衡量的是两个向量在方向上的一致性，而忽略它们的大小。
    该值范围在 -1.0 到 1.0 之间。值越接近 1.0，表示两个向量越相似；
    值越接近 -1.0，表示两个向量越不相似；0.0 表示两者正交（无关）。
    这在自然语言处理中常用于比较词向量、句子向量或文档向量的语义相似性。

    Args:
        embedding1: 第一个向量，可以是一个列表或一个 NumPy 数组。
        embedding2: 第二个向量，可以是一个列表或一个 NumPy 数组。

    Returns:
        float: 两个输入向量之间的余弦相似度，是一个介于 -1.0 和 1.0 之间的浮点数。
    """
    return np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
