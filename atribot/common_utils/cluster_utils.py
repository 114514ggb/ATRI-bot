from typing import Dict, List, Tuple


class ClusterUtils:
    """图连通分量工具：根据节点与边生成聚类结果"""

    @staticmethod
    def build_clusters(nodes: List[int], edges: List[Tuple[int, int]]) -> List[List[int]]:
        """使用并查集将边关系归并成簇"""
        if not nodes:
            return []

        parent: Dict[int, int] = {n: n for n in nodes}

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: int, b: int) -> None:
            ra = find(a)
            rb = find(b)
            if ra != rb:
                parent[rb] = ra

        for a, b in edges:
            if a in parent and b in parent:
                union(a, b)

        clusters: Dict[int, List[int]] = {}
        for n in nodes:
            root = find(n)
            clusters.setdefault(root, []).append(n)

        return list(clusters.values())
