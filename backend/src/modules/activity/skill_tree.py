"""技能树聚合纯函数（无 IO）：AC 提交 → 技能域/技能树。

契约见 docs/design/skill-tree.md §3。要点：
- 只统计 verdict=AC 的提交，按 (platform, problem_key) 去重（同题多次提交算一次，
  标签取并集、难度取最大值）；
- 每个节点（技能/域/总计）的 acCount 为其「去重 AC 题集合」大小，proficiency 由
  该集合的难度权重累加后套指数饱和（§3.3），maxDifficulty 为该集合最高原始难度；
- 无标签的提交（如 AtCoder）不参与技能映射，直接忽略；
- 未命中 TAG_TO_DOMAIN 的标签归 other（其他）域。
"""

import math
from collections import defaultdict
from collections.abc import Iterable

from adapters.base import Verdict
from modules.activity.models import Submission

# 技能域固定顺序（决定前端径向布局的扇区顺序，顶端正上方起始、顺时针）
DOMAIN_ORDER: list[tuple[str, str]] = [
    ("data_structures", "数据结构"),
    ("graphs", "图论"),
    ("dynamic_programming", "动态规划"),
    ("math", "数学"),
    ("geometry", "计算几何"),
    ("strings", "字符串"),
    ("greedy", "贪心"),
    ("search", "搜索"),
    ("implementation", "构造与实现"),
    ("basics", "基础算法"),
    ("bitmasks", "位运算"),
    ("games", "博弈"),
]

OTHER_DOMAIN_KEY = "other"
OTHER_DOMAIN_NAME = "其他"

# CF 标签 → 技能域 key（未列出的标签归 other）
TAG_TO_DOMAIN: dict[str, str] = {
    # 数据结构
    "data structures": "data_structures",
    "dsu": "data_structures",
    "trees": "data_structures",
    "hashing": "data_structures",
    # 图论
    "graphs": "graphs",
    "dfs and similar": "graphs",
    "shortest paths": "graphs",
    "flows": "graphs",
    "graph matchings": "graphs",
    "2-sat": "graphs",
    # 动态规划
    "dp": "dynamic_programming",
    # 数学
    "math": "math",
    "number theory": "math",
    "combinatorics": "math",
    "chinese remainder theorem": "math",
    "fft": "math",
    "matrices": "math",
    "probabilities": "math",
    # 计算几何
    "geometry": "geometry",
    # 字符串
    "strings": "strings",
    "string suffix structures": "strings",
    # 贪心
    "greedy": "greedy",
    # 搜索
    "brute force": "search",
    "meet-in-the-middle": "search",
    "divide and conquer": "search",
    # 构造与实现
    "implementation": "implementation",
    "constructive algorithms": "implementation",
    "expression parsing": "implementation",
    "interactive": "implementation",
    "schedules": "implementation",
    # 基础算法
    "binary search": "basics",
    "ternary search": "basics",
    "two pointers": "basics",
    "sortings": "basics",
    # 位运算
    "bitmasks": "bitmasks",
    # 博弈
    "games": "games",
}

# CF 标签 → 中文名（未列出的标签直接用原英文标签）
TAG_NAME: dict[str, str] = {
    "data structures": "数据结构",
    "dsu": "并查集",
    "trees": "树",
    "hashing": "哈希",
    "graphs": "图论基础",
    "dfs and similar": "DFS",
    "shortest paths": "最短路",
    "flows": "网络流",
    "graph matchings": "图匹配",
    "2-sat": "2-SAT",
    "dp": "动态规划",
    "math": "数学基础",
    "number theory": "数论",
    "combinatorics": "组合数学",
    "chinese remainder theorem": "中国剩余定理",
    "fft": "快速傅里叶变换",
    "matrices": "矩阵",
    "probabilities": "概率",
    "geometry": "计算几何",
    "strings": "字符串基础",
    "string suffix structures": "后缀结构",
    "greedy": "贪心",
    "brute force": "暴力枚举",
    "meet-in-the-middle": "折半搜索",
    "divide and conquer": "分治",
    "implementation": "实现",
    "constructive algorithms": "构造",
    "expression parsing": "表达式解析",
    "interactive": "交互题",
    "schedules": "调度",
    "binary search": "二分查找",
    "ternary search": "三分查找",
    "two pointers": "双指针",
    "sortings": "排序",
    "bitmasks": "位运算",
    "games": "博弈",
}

# 掌握度指数饱和的分母：score/3 越大越接近 1（见 design §3.3）
_SATURATION = 3.0


def difficulty_weight(difficulty: int | str | None) -> float:
    """题目难度 → 掌握度权重（未知/非数值给基础权重 0.5，CF rating 线性缩放）。"""
    if difficulty is None or isinstance(difficulty, str):
        return 0.5
    return max(0.5, float(difficulty) / 1000.0)


def proficiency(weights: list[float]) -> float:
    """累加权重 → 0..1 掌握度（指数饱和，早期增长快、后期放缓），保留 4 位小数。"""
    if not weights:
        return 0.0
    return round(min(1.0, 1.0 - math.exp(-sum(weights) / _SATURATION)), 4)


def _collect_ac(
    submissions: Iterable[Submission],
) -> dict[tuple[str, str], tuple[set[str], int | None]]:
    """按 (platform, problem_key) 去重 AC 题，返回 {key: (tags, max_difficulty)}。"""
    ac: dict[tuple[str, str], tuple[set[str], int | None]] = {}
    for s in submissions:
        if s.verdict != Verdict.AC:
            continue
        key = (s.platform, s.problem_key)
        tags = set(s.tags or [])
        difficulty = s.difficulty
        if key in ac:
            prev_tags, prev_diff = ac[key]
            tags |= prev_tags
            if difficulty is None:
                difficulty = prev_diff
            elif prev_diff is not None:
                difficulty = max(difficulty, prev_diff)
        ac[key] = (tags, difficulty)
    return ac


def _node(
    keys: set[tuple[str, str]],
    ac: dict[tuple[str, str], tuple[set[str], int | None]],
) -> dict[str, object]:
    """由问题 key 集合计算节点的 acCount / proficiency / maxDifficulty。"""
    weights = [difficulty_weight(ac[k][1]) for k in keys]
    difficulties = [ac[k][1] for k in keys if ac[k][1] is not None]
    return {
        "proficiency": proficiency(weights),
        "acCount": len(keys),
        "maxDifficulty": max(difficulties) if difficulties else None,
    }


def build_skill_tree(submissions: Iterable[Submission]) -> dict[str, object]:
    """AC 提交 → 技能树（domains + totals），无 IO。"""
    ac = _collect_ac(submissions)

    # 标签 → 命中该标签的问题 key 集合
    skill_keys: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for key, (tags, _diff) in ac.items():
        for tag in tags:
            skill_keys[tag].add(key)

    # 域 → 其下属全部技能的问题 key 并集
    domain_keys: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for tag, keys in skill_keys.items():
        domain = TAG_TO_DOMAIN.get(tag, OTHER_DOMAIN_KEY)
        domain_keys[domain] |= keys

    domains: list[dict[str, object]] = []
    ordered_domains = DOMAIN_ORDER + [(OTHER_DOMAIN_KEY, OTHER_DOMAIN_NAME)]
    for dkey, dname in ordered_domains:
        keys = domain_keys.get(dkey)
        if not keys:
            continue
        skills = []
        for tag in sorted(
            skill_keys,
            key=lambda t: (-len(skill_keys[t]), t),
        ):
            if TAG_TO_DOMAIN.get(tag, OTHER_DOMAIN_KEY) != dkey:
                continue
            skills.append(
                {
                    "key": tag,
                    "name": TAG_NAME.get(tag, tag),
                    "tag": tag,
                    **_node(skill_keys[tag], ac),
                }
            )
        domains.append(
            {
                "key": dkey,
                "name": dname,
                **_node(keys, ac),
                "skills": skills,
            }
        )

    # 总计 = 全部「有标签的 AC 题」的并集
    all_keys = set().union(*domain_keys.values()) if domain_keys else set()
    return {
        "domains": domains,
        "totals": _node(all_keys, ac),
    }
