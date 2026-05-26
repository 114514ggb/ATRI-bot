import numpy as np

from atribot.common_utils.similarity import calculate_similarity, jaro_winkler_similarity, levenshtein_distance


def test_levenshtein_distance():
    # 基础距离测试
    assert levenshtein_distance("kitten", "sitting") == 3
    assert levenshtein_distance("flaw", "lawn") == 4
    
    # 边界情况
    assert levenshtein_distance("", "test") == 4
    assert levenshtein_distance("test", "") == 4
    assert levenshtein_distance("same", "same") == 0
    assert levenshtein_distance("", "") == 0

def test_jaro_winkler_similarity():
    # 完全相同
    assert jaro_winkler_similarity("same", "same") == 1.0
    
    # 完全不同
    assert jaro_winkler_similarity("abc", "xyz") == 0.0
    
    # 包含相似片段
    sim = jaro_winkler_similarity("dixon", "dicksonx")
    assert 0.7 < sim < 0.9  # 分数应该在一定合理区间
    
    # 包含公共前缀
    sim_with_prefix = jaro_winkler_similarity("martha", "marhta")
    assert sim_with_prefix > 0.9  # jaro-winkler对共同前缀有加分
    
    # 边界测试
    assert jaro_winkler_similarity("", "abc") == 0.0

def test_calculate_similarity():
    # 纯方向对齐
    v1 = np.array([1.0, 0.0])
    v2 = np.array([0.0, 1.0])
    assert calculate_similarity(v1, v2) == 0.0
    
    v3 = [1.0, 0.0]
    v4 = [1.0, 0.0]
    assert calculate_similarity(v3, v4) == 1.0
    
    v5 = [1.0, 0.0]
    v6 = [-1.0, 0.0]
    assert calculate_similarity(v5, v6) == -1.0
