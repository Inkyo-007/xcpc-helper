"""UserStore 读写层测试：profile 往返、原子写、去重合并、损坏容错、名称校验。"""

import pytest

from core.exceptions import BadRequestError
from modules.activity.models import Account, Submission, Verdict
from modules.activity.store import UserStore


def make_store(tmp_path) -> UserStore:
    return UserStore(tmp_path / "user", "default")


def submission(sid: str, ts: int, verdict: Verdict = Verdict.AC) -> Submission:
    return Submission(
        platform="codeforces",
        handle="demo",
        submission_id=sid,
        problem_key="2245A",
        problem_name="X Axis",
        problem_url="https://codeforces.com/problemset/problem/2245/A",
        verdict=verdict,
        submitted_at=ts,
        language="GNU C++17",
    )


def test_profile_roundtrip(tmp_path):
    store = make_store(tmp_path)
    profile = store.load_profile()
    assert profile.id == "default"
    assert profile.accounts == []

    profile.accounts.append(Account(platform="codeforces", handle="demo"))
    store.save_profile(profile)

    loaded = store.load_profile()
    assert loaded.id == "default"
    assert loaded.accounts[0].handle == "demo"


def test_save_account_add_and_update(tmp_path):
    store = make_store(tmp_path)
    store.save_account(Account(platform="codeforces", handle="demo"))
    store.save_account(Account(platform="codeforces", handle="demo", last_synced_at=1000))

    profile = store.load_profile()
    assert len(profile.accounts) == 1
    assert profile.accounts[0].last_synced_at == 1000


def test_remove_account_deletes_file(tmp_path):
    store = make_store(tmp_path)
    store.save_account(Account(platform="codeforces", handle="demo"))
    store.merge_submissions("codeforces", "demo", [submission("1", 1000)])
    assert store.load_submissions("codeforces", "demo")[0]

    store.remove_account("codeforces", "demo")
    profile = store.load_profile()
    assert profile.accounts == []
    assert store.load_submissions("codeforces", "demo") == ([], 0)


def test_merge_deduplicates_and_sorts(tmp_path):
    store = make_store(tmp_path)
    store.merge_submissions("codeforces", "demo", [submission("1", 1000), submission("2", 2000)])
    # 重复 id + 新 id + 乱序
    added = store.merge_submissions(
        "codeforces", "demo",
        [submission("2", 2000), submission("3", 1500), submission("1", 1000)],
    )
    assert added == 1
    items, skipped = store.load_submissions("codeforces", "demo")
    assert skipped == 0
    assert [s.submission_id for s in items] == ["1", "3", "2"]  # 按时间升序
    assert items[1].submitted_at == 1500


def test_load_skips_corrupt_lines(tmp_path):
    store = make_store(tmp_path)
    path = store._submissions_file("codeforces", "demo")
    path.parent.mkdir(parents=True)
    path.write_text(
        submission("1", 1000).model_dump_json() + "\n"
        + "{not valid json}\n"
        + submission("2", 2000).model_dump_json() + "\n",
        encoding="utf-8",
    )
    items, skipped = store.load_submissions("codeforces", "demo")
    assert [s.submission_id for s in items] == ["1", "2"]
    assert skipped == 1


def test_profile_corrupt_falls_back_to_empty(tmp_path):
    store = make_store(tmp_path)
    (tmp_path / "user" / "default").mkdir(parents=True)
    (tmp_path / "user" / "default" / "profile.json").write_text(
        "{broken", encoding="utf-8"
    )
    profile = store.load_profile()
    assert profile.accounts == []


def test_invalid_handle_rejected(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(BadRequestError):
        store.merge_submissions("codeforces", "a/b", [submission("1", 1000)])
    with pytest.raises(BadRequestError):
        store.load_submissions("codeforces", "../evil")
