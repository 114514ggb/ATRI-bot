from typing import Dict, Iterable, List, Tuple


class ClusterUtils:
    """图连通分量工具：根据节点与边生成聚类结果"""

    @staticmethod
    def build_clusters(nodes: Iterable[int], edges: Iterable[Tuple[int, int]]) -> List[List[int]]:
        """使用并查集将边关系归并成簇"""
        
        if node_list := list(dict.fromkeys(nodes)):

            parent: Dict[int, int] = {n: n for n in node_list}
            rank: Dict[int, int] = {n: 0 for n in node_list}

            def find(x: int) -> int:
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            for a, b in edges:
                if a not in parent or b not in parent:
                    continue
                ra = find(a)
                rb = find(b)
                if ra == rb:
                    continue
                if rank[ra] < rank[rb]:
                    parent[ra] = rb
                elif rank[ra] > rank[rb]:
                    parent[rb] = ra
                else:
                    parent[rb] = ra
                    rank[ra] += 1

            clusters: Dict[int, List[int]] = {}
            for n in node_list:
                clusters.setdefault(find(n), []).append(n)

            return list(clusters.values())
        
        else:
            return []
