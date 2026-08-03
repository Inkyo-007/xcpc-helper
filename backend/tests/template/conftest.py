"""测试夹具：在临时目录中构造 content/ 样本。"""

from pathlib import Path

import pytest

README_FULL = """---
title: '线性筛（欧拉筛）'
updated: 2026-07-29
tags: ['素数', '积性函数']
source: '洛谷 P3383'
page: 'https://www.luogu.com.cn/problem/P3383'
priority: 5
---

每个合数只被最小质因子筛掉一次。
"""

CPP_CODE = "#include <bits/stdc++.h>\nusing namespace std;\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    """构造覆盖三种目录形态与中文路径的 content/ 样本。"""
    root = tmp_path / "content"

    # 形态一：代码文件直接在模板目录下（单版本）
    _write(root / "math" / "sieve" / "euler_sieve.cpp", CPP_CODE)
    _write(root / "math" / "sieve" / "README.md", README_FULL)

    # 形态二：多个副标签子目录（多版本）
    _write(root / "ds" / "dsu" / "path-compression" / "dsu.cpp", CPP_CODE)
    _write(
        root / "ds" / "dsu" / "path-compression" / "README.md",
        "---\ntitle: '并查集'\npriority: 4\n---\n\n路径压缩版。\n",
    )
    _write(root / "ds" / "dsu" / "with-weight" / "dsu_weight.cpp", CPP_CODE)
    _write(
        root / "ds" / "dsu" / "with-weight" / "README.md",
        "---\ntitle: '并查集'\ntags: '连通性'\n---\n\n带权版。\n",
    )

    # 形态三：仅一个副标签子目录（折叠为单版本）
    _write(root / "graph" / "tarjan" / "v1" / "tarjan.cpp", CPP_CODE)
    _write(
        root / "graph" / "tarjan" / "v1" / "README.md",
        "---\ntitle: 'Tarjan SCC'\nupdated: 'bad-date'\n---\n",
    )

    # 中文路径
    _write(root / "字符串" / "哈希" / "str_hash.cpp", CPP_CODE)
    _write(
        root / "字符串" / "哈希" / "README.md",
        "---\ntitle: '字符串哈希（双模）'\npage: 'https://example.com'\n---\n\n双模不撞。\n",
    )

    # 异常样本：缺少 title / 缺代码文件
    _write(root / "misc" / "broken-no-title" / "x.cpp", CPP_CODE)
    _write(root / "misc" / "broken-no-title" / "README.md", "---\ntags: [a]\n---\n")
    _write(root / "misc" / "broken-no-code" / "README.md", "---\ntitle: '孤儿'\n---\n")

    return root
