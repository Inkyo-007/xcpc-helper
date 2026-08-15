"""AtCoder 适配器测试：录制 JSON fixture 解析、升序翻页、增量/全量、目录缓存、404 验证。"""

import copy
import json
import time
from pathlib import Path

import httpx
import pytest

from adapters.atcoder import AtCoderAdapter
from adapters.atcoder.api_models import AtProblem, AtProblemModel, AtSubmissionRow
from adapters.atcoder.normalize import map_verdict, problem_url
from adapters.base import PlatformError, PlatformSubmission, UserNotFoundError, Verdict
from adapters.net import HttpFetcher

FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE = json.loads(
    (FIXTURES / "at_submissions_sample.json").read_text(encoding="utf-8")
)
PROBLEMS = json.loads((FIXTURES / "at_problems_sample.json").read_text(encoding="utf-8"))
MODELS = json.loads(
    (FIXTURES / "at_problem_models_sample.json").read_text(encoding="utf-8")
)
PROBLEMS_TYPED = [AtProblem.model_validate(p) for p in PROBLEMS]
MODELS_TYPED = {k: AtProblemModel.model_validate(v) for k, v in MODELS.items()}

# 全量同步策略参数（生产由 Settings 注入，测试直接传）
FULL_WINDOW_DAYS = 370
FULL_MIN_ROWS = 5000

SUBMISSIONS_PATH = "/atcoder/atcoder-api/v3/user/submissions"
PROBLEMS_PATH = "/atcoder/resources/problems.json"
MODELS_PATH = "/atcoder/resources/problem-models.json"


def make_adapter(handler) -> tuple[AtCoderAdapter, HttpFetcher]:
    fetcher = HttpFetcher(transport=httpx.MockTransport(handler), base_backoff=0.01)
    adapter = AtCoderAdapter(fetcher)
    adapter.min_interval = 0  # 测试禁用真实限流等待（限流本身由 test_net 覆盖）
    return adapter, fetcher


def row(id_: int, ts: int, result: str = "AC", problem_id: str = "ahc052_a") -> dict:
    """基于录制样本复制一行并覆盖关键字段。"""
    r = copy.deepcopy(SAMPLE[0])
    r["id"] = id_
    r["epoch_second"] = ts
    r["result"] = result
    r["problem_id"] = problem_id
    return r


def catalog_handler(pages: list[list[dict]]):
    """按路径分发：提交分页 + 题目目录；记录 submissions 请求的 from_second。"""

    requested_from: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == SUBMISSIONS_PATH:
            from_second = int(request.url.params["from_second"])
            requested_from.append(from_second)
            idx = len(requested_from) - 1
            rows = pages[idx] if idx < len(pages) else []
            return httpx.Response(200, json=rows)
        if path == PROBLEMS_PATH:
            return httpx.Response(200, json=PROBLEMS)
        if path == MODELS_PATH:
            return httpx.Response(200, json=MODELS)
        raise AssertionError(f"未预期的请求: {request.url}")

    return handler, requested_from


async def fetch(adapter, since=None, min_rows=FULL_MIN_ROWS):
    return await adapter.fetch_submissions(
        "chokudai",
        since=since,
        full_window_days=FULL_WINDOW_DAYS,
        full_min_rows=min_rows,
    )


# ===== verify =====


async def test_verify_ok():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "atcoder.jp"
        assert request.url.path == "/users/ChOkUdAi"
        return httpx.Response(
            200,
            text="<html><head><title>choku&#100;ai - AtCoder</title></head></html>",
        )

    adapter, fetcher = make_adapter(handler)
    try:
        info = await adapter.verify("ChOkUdAi")
        assert info.handle == "chokudai"
        assert info.avatar is None
    finally:
        await fetcher.aclose()


async def test_verify_unrecognized_profile_html_is_platform_error():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><head><title>AtCoder</title></head></html>")

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(PlatformError, match="缺少可识别的标题"):
            await adapter.verify("chokudai")
    finally:
        await fetcher.aclose()


async def test_verify_404_is_user_not_found():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(UserNotFoundError):
            await adapter.verify("no_such_user_xyz")
    finally:
        await fetcher.aclose()


async def test_verify_other_4xx_is_platform_error():
    """非 404 的 4xx（如 403 反爬）维持平台故障，不误报用户不存在。"""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="forbidden")

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(PlatformError) as exc_info:
            await adapter.verify("chokudai")
        assert not isinstance(exc_info.value, UserNotFoundError)
    finally:
        await fetcher.aclose()


# ===== fetch_submissions =====


async def test_fetch_maps_fields_with_catalog():
    """字段归一化：题名/难度来自目录，URL 按 contest/problem 生成。"""
    handler, _ = catalog_handler([SAMPLE])
    adapter, fetcher = make_adapter(handler)
    try:
        items = await fetch(adapter)
        assert [s.submission_id for s in items] == [
            "68710320",
            "68710893",
            "70291592",
        ]
        first = items[0]
        assert first.problem_key == "ahc052_a"
        assert first.problem_name == "Single Controller Multiple Robots"
        assert first.problem_url == "https://atcoder.jp/contests/ahc052/tasks/ahc052_a"
        assert first.difficulty == 3822
        assert first.verdict is Verdict.AC
        assert first.language == "C# 11.0 AOT (.NET 7.0.7)"
        assert items[2].verdict is Verdict.TLE
    finally:
        await fetcher.aclose()


async def test_fetch_incremental_passes_since_as_from_second():
    """增量：首个请求的 from_second 即游标（含边界，游标当秒提交重复拉）。"""
    now = int(time.time())
    since = now - 2 * 86400
    handler, requested_from = catalog_handler(
        [[row(3, since), row(4, since + 60)]]  # 游标当秒的提交应被拉取
    )
    adapter, fetcher = make_adapter(handler)
    try:
        items = await fetch(adapter, since=since)
        assert requested_from[0] == since
        assert [s.submission_id for s in items] == ["3", "4"]
    finally:
        await fetcher.aclose()


async def test_fetch_paginates_and_dedups_overlap(monkeypatch):
    """升序翻页：from_second 含边界导致页间同秒重叠，按 id 去重。"""
    monkeypatch.setattr("adapters.atcoder.PAGE_LIMIT", 2)
    now = int(time.time())
    handler, requested_from = catalog_handler(
        [
            [row(1, now - 100), row(2, now - 50)],  # 满页（2 条）→ 翻页
            [row(2, now - 50), row(3, now - 10)],  # 与上页末条同秒重叠 → 去重
            [row(4, now)],  # 短页 → 停止
        ]
    )
    adapter, fetcher = make_adapter(handler)
    try:
        items = await fetch(adapter, since=now - 200)
        assert [s.submission_id for s in items] == ["1", "2", "3", "4"]
        assert requested_from == [now - 200, now - 50, now - 10]
    finally:
        await fetcher.aclose()


async def test_fetch_stops_on_stalled_full_page(monkeypatch):
    """满页但无新 id（同秒提交 ≥ 单页上限）时停止，防死循环。"""
    monkeypatch.setattr("adapters.atcoder.PAGE_LIMIT", 2)
    now = int(time.time())
    same_second = [row(1, now), row(2, now)]
    handler, requested_from = catalog_handler([same_second, same_second])
    adapter, fetcher = make_adapter(handler)
    try:
        items = await fetch(adapter, since=now - 100)
        assert [s.submission_id for s in items] == ["1", "2"]
        assert len(requested_from) == 2  # 第二页无新 id 即停，不再翻页
    finally:
        await fetcher.aclose()


async def test_fetch_full_falls_back_to_all_history():
    """全量：窗口内不足 full_min_rows 时退到 from_second=0 拉全部历史。"""
    now = int(time.time())
    old_ts = now - 800 * 86400  # 窗口外的历史提交
    pages_by_from: dict[int, list[dict]] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == SUBMISSIONS_PATH:
            from_second = int(request.url.params["from_second"])
            pages_by_from[from_second] = []
            if from_second == 0:
                return httpx.Response(200, json=[row(1, old_ts), row(2, now - 100)])
            return httpx.Response(200, json=[row(2, now - 100)])
        if path == PROBLEMS_PATH:
            return httpx.Response(200, json=PROBLEMS)
        if path == MODELS_PATH:
            return httpx.Response(200, json=MODELS)
        raise AssertionError(f"未预期的请求: {request.url}")

    adapter, fetcher = make_adapter(handler)
    try:
        items = await fetch(adapter, min_rows=5)
        # 窗口内仅 1 条 < 5 → 触发全历史回拉；重叠行按 id 去重
        assert [s.submission_id for s in items] == ["2", "1"]
        assert 0 in pages_by_from
    finally:
        await fetcher.aclose()


async def test_fetch_full_skips_fallback_when_enough_rows():
    """全量：窗口内条数达标时不回拉全历史。"""
    now = int(time.time())
    handler, requested_from = catalog_handler(
        [[row(i, now - i * 60) for i in range(5)]]
    )
    adapter, fetcher = make_adapter(handler)
    try:
        items = await fetch(adapter, min_rows=5)
        assert len(items) == 5
        assert 0 not in requested_from  # 未触发全历史回拉
    finally:
        await fetcher.aclose()


async def test_fetch_catalog_cached_across_calls():
    """题目目录在 TTL 内只拉一次，后续同步复用缓存。"""
    now = int(time.time())
    catalog_calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal catalog_calls
        path = request.url.path
        if path == SUBMISSIONS_PATH:
            return httpx.Response(200, json=[row(1, now - 100)])
        if path == PROBLEMS_PATH:
            catalog_calls += 1
            return httpx.Response(200, json=PROBLEMS)
        if path == MODELS_PATH:
            return httpx.Response(200, json=MODELS)
        raise AssertionError(f"未预期的请求: {request.url}")

    adapter, fetcher = make_adapter(handler)
    try:
        await fetch(adapter, since=now - 200)
        await fetch(adapter, since=now - 200)
        assert catalog_calls == 1
    finally:
        await fetcher.aclose()


async def test_fetch_problems_catalog_failure_raises():
    """problems.json 失败（题名为核心字段）抛 PlatformError，本次同步降级重试。"""

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == PROBLEMS_PATH:
            return httpx.Response(200, text="<html>bad gateway</html>")
        if request.url.path == SUBMISSIONS_PATH:
            return httpx.Response(200, json=SAMPLE)
        raise AssertionError(f"未预期的请求: {request.url}")

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(PlatformError):
            await fetch(adapter)
    finally:
        await fetcher.aclose()


async def test_fetch_models_failure_degrades_difficulty():
    """problem-models.json 失败（非关键字段）：difficulty 置空，同步继续。"""
    handler_ok, _ = catalog_handler([SAMPLE])

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == MODELS_PATH:
            return httpx.Response(200, text="<html>bad gateway</html>")
        return await handler_ok(request)

    adapter, fetcher = make_adapter(handler)
    try:
        items = await fetch(adapter)
        assert len(items) == 3
        assert all(s.difficulty is None for s in items)
        # 题名不受难度模型失败影响
        assert items[0].problem_name == "Single Controller Multiple Robots"
    finally:
        await fetcher.aclose()


async def test_fetch_missing_problem_falls_back_to_problem_id():
    """目录缺题：problem_name 兜底 problem_id，difficulty 为 None。"""
    handler, _ = catalog_handler([[row(1, int(time.time()), problem_id="unknown_p")]])
    adapter, fetcher = make_adapter(handler)
    try:
        items = await fetch(adapter, since=int(time.time()) - 100)
        assert items[0].problem_key == "unknown_p"
        assert items[0].problem_name == "unknown_p"
        assert items[0].difficulty is None
        assert items[0].problem_url == "https://atcoder.jp/contests/ahc052/tasks/unknown_p"
    finally:
        await fetcher.aclose()


async def test_fetch_row_missing_epoch_second_raises():
    """提交行缺 epoch_second：必填校验失败抛 PlatformError。

    时间戳若默认 0，增量拉取会把它当作"旧于游标"提前终止，
    静默丢弃同页后续新提交；必须暴露为平台格式异常。
    """

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == SUBMISSIONS_PATH:
            return httpx.Response(200, json=[{"id": 1}])
        if path == PROBLEMS_PATH:
            return httpx.Response(200, json=PROBLEMS)
        if path == MODELS_PATH:
            return httpx.Response(200, json=MODELS)
        raise AssertionError(f"未预期的请求: {request.url}")

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(PlatformError):
            await fetch(adapter)
    finally:
        await fetcher.aclose()


async def test_fetch_non_json_response_raises():
    """网关返回 HTML 错误页：收敛为 PlatformError 而非 JSONDecodeError 逃逸。"""

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == SUBMISSIONS_PATH:
            return httpx.Response(200, text="<html>Service Unavailable</html>")
        if path == PROBLEMS_PATH:
            return httpx.Response(200, json=PROBLEMS)
        if path == MODELS_PATH:
            return httpx.Response(200, json=MODELS)
        raise AssertionError(f"未预期的请求: {request.url}")

    adapter, fetcher = make_adapter(handler)
    try:
        with pytest.raises(PlatformError):
            await fetch(adapter)
    finally:
        await fetcher.aclose()


# ===== 归一化纯函数 =====


def test_verdict_mapping():
    assert map_verdict("AC") is Verdict.AC
    assert map_verdict("WA") is Verdict.WA
    assert map_verdict("TLE") is Verdict.TLE
    assert map_verdict("MLE") is Verdict.MLE
    assert map_verdict("RE") is Verdict.RE
    assert map_verdict("CE") is Verdict.CE
    assert map_verdict("OLE") is Verdict.OLE
    assert map_verdict("WJ") is Verdict.JG
    assert map_verdict("WR") is Verdict.JG
    assert map_verdict("JUDGING") is Verdict.JG
    assert map_verdict("IE") is Verdict.UKE
    assert map_verdict("QLE") is Verdict.UKE
    assert map_verdict("") is Verdict.UKE
    assert map_verdict("SOME_FUTURE_VERDICT") is Verdict.UKE


def test_problem_url():
    assert (
        problem_url("ahc052", "ahc052_a")
        == "https://atcoder.jp/contests/ahc052/tasks/ahc052_a"
    )
    assert problem_url("", "") == "https://atcoder.jp"


def test_to_submission_row_mapping():
    row_ = AtSubmissionRow.model_validate(SAMPLE[0])
    adapter = AtCoderAdapter.__new__(AtCoderAdapter)
    adapter._problems = {p.id: p for p in PROBLEMS_TYPED}
    adapter._models = MODELS_TYPED
    s = adapter._to_submission(row_)
    assert isinstance(s, PlatformSubmission)
    assert s.submission_id == "68710320"
    assert s.submitted_at == 1755940675
    assert s.problem_name == "Single Controller Multiple Robots"
    assert s.difficulty == 3822
