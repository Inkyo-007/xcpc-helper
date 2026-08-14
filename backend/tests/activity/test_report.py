"""report 纯函数 + LlmClient（MockTransport）+ service 层报告降级测试。"""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from adapters.base import Verdict
from adapters.net import HttpFetcher
from core.config import Settings
from modules.activity.aggregate import overview_stats
from modules.activity.analysis import build_analysis
from modules.activity.models import Submission
from modules.activity.report import build_prompt, build_rule_report
from services.activity.llm import LlmClient, LlmError
from services.activity.service import ActivityService

TZ = timezone(timedelta(hours=8))  # UTC+8 固定偏移，测试不依赖系统时区


def ts_today(hour: int, minute: int = 0) -> int:
    """系统本地「今天」某时刻的 UTC 时间戳。"""
    d = datetime.now(TZ).date()
    return int(datetime(d.year, d.month, d.day, hour, minute, tzinfo=TZ).timestamp())


def sub(
    sid: str,
    key: str = "2245A",
    verdict: str = "AC",
    tags: tuple[str, ...] = ("math",),
    difficulty: int | None = 800,
    platform: str = "codeforces",
    ts: int | None = None,
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
        submitted_at=ts if ts is not None else ts_today(10),
        language="GNU C++17",
    )


def sample_submissions() -> list[Submission]:
    """构造：dp 高投入低通过 + graphs 全 TLE + WA/TLE 占比高。"""
    return [
        sub("1", key="A", verdict="AC", tags=("dp",), difficulty=800, ts=ts_today(10)),
        sub("2", key="B", verdict="WA", tags=("dp",), difficulty=800, ts=ts_today(10)),
        sub("3", key="C", verdict="WA", tags=("dp",), difficulty=900, ts=ts_today(10)),
        sub("4", key="D", verdict="WA", tags=("dp",), difficulty=900, ts=ts_today(11)),
        sub("5", key="E", verdict="TLE", tags=("graphs",), difficulty=1200, ts=ts_today(11)),
        sub("6", key="F", verdict="TLE", tags=("graphs",), difficulty=1300, ts=ts_today(11)),
    ]


def sample_data() -> tuple[dict, dict]:
    items = sample_submissions()
    return build_analysis(items, tz=TZ), overview_stats(items, tz=TZ)


# ===== build_rule_report =====


def test_rule_report_has_all_sections():
    analysis, overview = sample_data()
    text = build_rule_report(analysis, overview)
    for heading in [
        "总体概况",
        "难度分布解读",
        "提交质量",
        "训练节奏",
        "薄弱点清单",
        "下一步建议",
    ]:
        assert heading in text


def test_rule_report_is_data_driven():
    analysis, overview = sample_data()
    text = build_rule_report(analysis, overview)
    # WA/TLE 占比高 → 出现相应提示
    assert "WA 占比较高" in text
    assert "TLE 占比较高" in text
    # 主力分档与低通过率档位
    assert "主力分档" in text
    assert "≤1199" in text
    assert "通过率较低的档位" in text
    # 薄弱点逐条含中文名 + 规则化 suggestion
    assert "动态规划" in text
    assert "图论基础" in text
    assert "基础薄弱，建议从该标签入门题系统刷起" in text


def test_rule_report_weak_points_have_suggestion():
    analysis, overview = sample_data()
    text = build_rule_report(analysis, overview)
    for name in ("动态规划", "图论基础"):
        assert f"**{name}**" in text
    # 每条薄弱点行都带 suggestion 文案
    assert "基础薄弱，建议从该标签入门题系统刷起" in text


def test_rule_report_deterministic():
    analysis, overview = sample_data()
    assert build_rule_report(analysis, overview) == build_rule_report(analysis, overview)


def test_rule_report_empty_data():
    analysis = build_analysis([], tz=TZ)
    overview = overview_stats([], tz=TZ)
    text = build_rule_report(analysis, overview)
    assert "总体概况" in text
    assert "下一步建议" in text
    assert "暂无" in text


# ===== build_prompt =====


def test_build_prompt_structure_and_data():
    analysis, overview = sample_data()
    msgs = build_prompt(analysis, overview)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert "教练" in msgs[0]["content"]
    content = msgs[1]["content"]
    # 紧凑 JSON 含关键数字（总解题/总提交）
    assert '"totalSolved":1' in content
    assert '"totalSubmissions":6' in content
    # ensure_ascii=False：中文原样保留（薄弱点中文名）
    assert "动态规划" in content


# ===== LlmClient =====


def _client(handler) -> LlmClient:
    return LlmClient(
        base_url="https://api.example.com/v1/",
        api_key="sk-test",
        model="deepseek-chat",
        timeout=5.0,
        max_tokens=2048,
        transport=httpx.MockTransport(handler),
    )


async def test_llm_complete_ok():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.example.com/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer sk-test"
        body = json.loads(request.content)
        assert body["model"] == "deepseek-chat"
        assert body["messages"] == [{"role": "user", "content": "hi"}]
        assert body["max_tokens"] == 2048
        assert body["temperature"] == 0.4
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "报告内容"}}]}
        )

    client = _client(handler)
    content = await client.complete([{"role": "user", "content": "hi"}])
    assert content == "报告内容"
    await client.aclose()


async def test_llm_complete_non_2xx_raises():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="oops")

    client = _client(handler)
    try:
        with pytest.raises(LlmError):
            await client.complete([{"role": "user", "content": "hi"}])
    finally:
        await client.aclose()


async def test_llm_complete_missing_choices_raises():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"foo": "bar"})

    client = _client(handler)
    try:
        with pytest.raises(LlmError):
            await client.complete([{"role": "user", "content": "hi"}])
    finally:
        await client.aclose()


async def test_llm_complete_network_error_raises():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    try:
        with pytest.raises(LlmError):
            await client.complete([{"role": "user", "content": "hi"}])
    finally:
        await client.aclose()


# ===== service 层降级 =====


class _FailingLlmClient:
    """注入的假 LLM 客户端：complete 恒抛 LlmError（不继承 LlmClient）。"""

    async def complete(self, messages: list[dict]) -> str:
        raise LlmError("模拟 LLM 故障")


class _OkLlmClient:
    """注入的假 LLM 客户端：complete 返回固定内容。"""

    async def complete(self, messages: list[dict]) -> str:
        return "# 报告\n\nLLM 生成内容"


async def _noop_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(404)


def _make_service(tmp_path, *, llm_api_key: str = "", llm_client=None) -> ActivityService:
    fetcher = HttpFetcher(
        transport=httpx.MockTransport(_noop_handler), base_backoff=0.01
    )
    return ActivityService(
        Settings(user_data_dir=tmp_path / "user", llm_api_key=llm_api_key),
        fetcher,
        llm_client=llm_client,
    )


async def test_report_rule_when_unconfigured(tmp_path):
    svc = _make_service(tmp_path, llm_api_key="")
    try:
        out = await svc.report(None)
    finally:
        await svc.aclose()
    assert out.source == "rule"
    assert out.model is None
    assert out.note is not None and "未配置" in out.note
    assert "总体概况" in out.content


async def test_report_llm_error_falls_back_to_rule(tmp_path):
    svc = _make_service(
        tmp_path, llm_api_key="sk-test", llm_client=_FailingLlmClient()
    )
    try:
        out = await svc.report(None)
    finally:
        await svc.aclose()
    assert out.source == "rule"
    assert out.note is not None and "降级" in out.note
    assert "总体概况" in out.content


async def test_report_llm_success(tmp_path):
    svc = _make_service(tmp_path, llm_api_key="sk-test", llm_client=_OkLlmClient())
    try:
        out = await svc.report(None)
    finally:
        await svc.aclose()
    assert out.source == "llm"
    assert out.model == "deepseek-chat"
    assert out.note is None
    assert out.content == "# 报告\n\nLLM 生成内容"


async def test_report_config(tmp_path):
    svc = _make_service(tmp_path, llm_api_key="")
    try:
        cfg = svc.report_config()
    finally:
        await svc.aclose()
    assert cfg.configured is False
    assert cfg.model == "deepseek-chat"
    assert cfg.baseUrl == "https://api.deepseek.com/v1"

    svc2 = _make_service(tmp_path, llm_api_key="sk-test")
    try:
        assert svc2.report_config().configured is True
    finally:
        await svc2.aclose()
