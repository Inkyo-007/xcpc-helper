"""平台适配契约测试：能力方法默认抛错、rating/contests 骨架、异常体系。"""

import pytest

from adapters.base import (
    AdapterError,
    AuthExpiredError,
    AuthMode,
    Capability,
    CapabilityNotSupportedError,
    ContestInfo,
    Credentials,
    PlatformAdapter,
    PlatformError,
    RatingPoint,
    UserNotFoundError,
)


class BareAdapter(PlatformAdapter):
    """未实现任何能力方法的平台（如牛客第一期只有 rating 的形态）。"""

    platform_id = "bare"
    name = "Bare"
    capabilities = frozenset({Capability.RATING})
    auth = AuthMode.NONE
    min_interval = 0.0


async def test_unimplemented_capabilities_raise():
    adapter = BareAdapter()
    with pytest.raises(CapabilityNotSupportedError):
        await adapter.verify("demo")
    with pytest.raises(CapabilityNotSupportedError):
        # fetch_submissions 为异步生成器：首次取批时抛契约违约
        async for _batch in adapter.fetch_submissions(
            "demo", since=None, full_window_days=370, full_min_rows=5000
        ):
            pass
    with pytest.raises(CapabilityNotSupportedError):
        await adapter.fetch_contests()


async def test_rating_capability_contract():
    """RATING 能力方法签名存在且默认抛错（后续增量，第一期不实现）。"""
    assert Capability.RATING in BareAdapter.capabilities
    adapter = BareAdapter()
    with pytest.raises(CapabilityNotSupportedError):
        await adapter.fetch_rating_history("demo")


def test_rating_point_model():
    point = RatingPoint(time=1755100000, rating=2400, contest_name="Codeforces Round #1")
    assert point.rating == 2400
    assert point.contest_name == "Codeforces Round #1"


def test_contest_info_model():
    contest = ContestInfo(
        contest_id="2245",
        name="Codeforces Round (Div. 2)",
        start_time=1755100000,
        duration_seconds=7200,
    )
    assert contest.duration_seconds == 7200


def test_contests_capability_defined():
    assert Capability.CONTESTS == "contests"


def test_exception_hierarchy():
    """异常体系：AuthExpired 与平台故障同属 AdapterError 但语义独立。"""
    assert issubclass(AuthExpiredError, AdapterError)
    assert issubclass(PlatformError, AdapterError)
    assert issubclass(UserNotFoundError, AdapterError)
    assert issubclass(CapabilityNotSupportedError, AdapterError)


def test_credentials_model():
    creds = Credentials(cookies={"_uid": "123"}, headers={"X-Token": "abc"})
    assert creds.cookies["_uid"] == "123"
    assert creds.headers["X-Token"] == "abc"
