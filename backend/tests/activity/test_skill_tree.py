"""skill_tree 纯函数测试：去重口径、标签→域映射、掌握度公式、节点排序。"""

from adapters.base import Verdict
from modules.activity.models import Submission
from modules.activity.skill_tree import build_skill_tree, proficiency


def sub(
    sid: str,
    key: str = "2245A",
    verdict: str = "AC",
    tags: tuple[str, ...] = ("math",),
    difficulty: int | None = 800,
    platform: str = "codeforces",
) -> Submission:
    return Submission(
        platform=platform,
        handle="demo",
        submission_id=sid,
        problem_key=key,
        problem_name="X",
        problem_url="https://codeforces.com/contest/2245/problem/A",
        difficulty=difficulty,
        tags=list(tags),
        verdict=Verdict(verdict),
        submitted_at=1786566000,
        language="GNU C++17",
    )


def domains_by_key(tree: dict) -> dict[str, dict]:
    return {d["key"]: d for d in tree["domains"]}


def skills_by_tag(domain: dict) -> dict[str, dict]:
    return {s["tag"]: s for s in domain["skills"]}


# ===== 掌握度公式 =====


def test_proficiency_empty_is_zero():
    assert proficiency([]) == 0.0


def test_proficiency_saturates_at_one():
    assert proficiency([2.0] * 100) == 1.0


def test_proficiency_monotonic():
    low = proficiency([0.8])
    high = proficiency([0.8, 1.2, 2.0])
    assert 0.0 < low < high < 1.0


def test_weight_unknown_difficulty_fallback():
    """difficulty=None 给基础权重：两条无难度 AC 题也有非零掌握度。"""
    tree = build_skill_tree(
        [sub("1", difficulty=None), sub("2", key="2245B", difficulty=None)]
    )
    domain = domains_by_key(tree)["math"]
    assert domain["acCount"] == 2
    assert domain["proficiency"] > 0.0
    assert domain["maxDifficulty"] is None


# ===== 去重与过滤 =====


def test_empty_submissions():
    tree = build_skill_tree([])
    assert tree["domains"] == []
    assert tree["totals"]["acCount"] == 0
    assert tree["totals"]["proficiency"] == 0.0
    assert tree["totals"]["maxDifficulty"] is None


def test_dedup_and_ac_only():
    """同题 WA+AC+AC 只算一个 AC；TLE/UKE 不计。"""
    tree = build_skill_tree(
        [
            sub("1", key="2245A", verdict="WA"),
            sub("2", key="2245A", verdict="AC"),
            sub("3", key="2245A", verdict="AC"),
            sub("4", key="2245B", verdict="TLE"),
            sub("5", key="2245C", verdict="UKE"),
        ]
    )
    domain = domains_by_key(tree)["math"]
    assert domain["acCount"] == 1
    assert len(domain["skills"]) == 1
    assert domain["skills"][0]["acCount"] == 1


def test_no_tag_submission_ignored():
    """无标签提交（如 AtCoder）不参与技能映射。"""
    tree = build_skill_tree([sub("1", tags=(), platform="atcoder", difficulty=1000)])
    assert tree["domains"] == []
    assert tree["totals"]["acCount"] == 0


# ===== 标签 → 域映射 =====


def test_tag_maps_to_domain():
    tree = build_skill_tree([sub("1", tags=("dp",))])
    assert "dynamic_programming" in domains_by_key(tree)
    dp = domains_by_key(tree)["dynamic_programming"]
    assert dp["skills"][0]["tag"] == "dp"
    assert dp["skills"][0]["name"] == "动态规划"


def test_unknown_tag_goes_other():
    tree = build_skill_tree([sub("1", tags=("some-new-tag",))])
    other = domains_by_key(tree)["other"]
    assert other["name"] == "其他"
    assert other["skills"][0]["tag"] == "some-new-tag"
    # 未命中映射：技能名回退为原标签
    assert other["skills"][0]["name"] == "some-new-tag"


def test_multitag_spans_multiple_domains():
    """一道题带多个标签，分别计入各自技能域，域间不互相排他。"""
    tree = build_skill_tree([sub("1", tags=("dp", "graphs", "math"))])
    keys = set(domains_by_key(tree))
    assert {"dynamic_programming", "graphs", "math"} <= keys
    assert domains_by_key(tree)["math"]["acCount"] == 1
    assert domains_by_key(tree)["graphs"]["acCount"] == 1


def test_same_domain_multiple_tags_dedup():
    """同域多标签（dsu+trees）只在该域计一题，但拆成两个技能节点。"""
    tree = build_skill_tree([sub("1", tags=("dsu", "trees"), difficulty=1600)])
    ds = domains_by_key(tree)["data_structures"]
    assert ds["acCount"] == 1
    assert set(skills_by_tag(ds)) == {"dsu", "trees"}


# ===== 难度与排序 =====


def test_max_difficulty():
    tree = build_skill_tree(
        [
            sub("1", key="2245A", tags=("math",), difficulty=800),
            sub("2", key="2245B", tags=("math",), difficulty=2400),
            sub("3", key="2245C", tags=("greedy",), difficulty=1200),
        ]
    )
    math = domains_by_key(tree)["math"]
    assert math["maxDifficulty"] == 2400
    assert tree["totals"]["maxDifficulty"] == 2400
    assert domains_by_key(tree)["greedy"]["maxDifficulty"] == 1200


def test_harder_problem_raises_proficiency():
    """相同题数下，难度更高的标签掌握度更高。"""
    easy = build_skill_tree([sub("1", tags=("dp",), difficulty=800)])
    hard = build_skill_tree([sub("1", tags=("dp",), difficulty=2400)])
    assert (
        domains_by_key(hard)["dynamic_programming"]["proficiency"]
        > domains_by_key(easy)["dynamic_programming"]["proficiency"]
    )


def test_skills_sorted_by_ac_count_desc():
    tree = build_skill_tree(
        [
            sub("1", key="A", tags=("greedy",)),
            sub("2", key="B", tags=("math",)),
            sub("3", key="C", tags=("math",)),
            sub("4", key="D", tags=("math",)),
        ]
    )
    math = domains_by_key(tree)["math"]
    counts = [s["acCount"] for s in math["skills"]]
    assert counts == sorted(counts, reverse=True)


def test_domain_order_follows_declared_order():
    from modules.activity.skill_tree import DOMAIN_ORDER

    tree = build_skill_tree(
        [
            sub("1", tags=("games",)),
            sub("2", tags=("math",)),
            sub("3", tags=("dp",)),
        ]
    )
    keys = [d["key"] for d in tree["domains"]]
    expected = [d[0] for d in DOMAIN_ORDER if d[0] in keys]
    assert keys == expected
