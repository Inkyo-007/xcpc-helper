"""UserStore 读写层测试：profile 往返、原子写、去重合并、损坏容错、名称校验、用户组目录管理。"""

import pytest

from adapters.base import Credentials
from core.exceptions import BadRequestError, ConflictError, NotFoundError
from modules.activity.models import Account, Submission, Verdict
from modules.activity.store import (
    EXAMPLE_GROUP,
    UserStore,
    create_group,
    delete_group,
    list_groups,
    rename_group,
)


def make_store(tmp_path) -> UserStore:
    return UserStore(tmp_path / "user", "default")


def submission(sid: str, ts: int, verdict: Verdict = Verdict.AC) -> Submission:
    return Submission(
        platform="codeforces",
        handle="demo",
        submission_id=sid,
        problem_key="2245A",
        problem_name="X Axis",
        problem_url="https://codeforces.com/contest/2245/problem/A",
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


# ===== 用户组目录管理 =====


def test_profile_roundtrip_with_profile_fields(tmp_path):
    store = make_store(tmp_path)
    profile = store.load_profile()
    profile.id = "我的昵称"
    profile.signature = "菜就多练"
    profile.avatar = "data:image/jpeg;base64,abc"
    store.save_profile(profile)

    loaded = store.load_profile()
    assert loaded.id == "我的昵称"
    assert loaded.signature == "菜就多练"
    assert loaded.avatar == "data:image/jpeg;base64,abc"


def test_create_group_initializes_profile(tmp_path):
    root = tmp_path / "user"
    create_group(root, "第一组")
    groups = list_groups(root)
    assert groups == ["第一组"]
    profile = UserStore(root, "第一组").load_profile()
    # 信息卡 ID 初始为目录名（之后独立编辑）
    assert profile.id == "第一组"
    assert profile.accounts == []


def test_create_group_conflict(tmp_path):
    root = tmp_path / "user"
    create_group(root, "groupA")
    with pytest.raises(ConflictError):
        create_group(root, "groupA")


def test_list_groups_excludes_example_and_hidden(tmp_path):
    root = tmp_path / "user"
    create_group(root, "B组")
    create_group(root, "A组")
    # 模拟 example 样例目录与隐藏目录
    (root / EXAMPLE_GROUP).mkdir(exist_ok=True)
    (root / ".hidden").mkdir()
    assert list_groups(root) == ["A组", "B组"]


def test_rename_group_moves_data(tmp_path):
    root = tmp_path / "user"
    create_group(root, "旧名")
    store = UserStore(root, "旧名")
    store.merge_submissions("codeforces", "demo", [submission("1", 1000)])
    store.save_account(Account(platform="codeforces", handle="demo", last_synced_at=1000))

    rename_group(root, "旧名", "新名")
    assert list_groups(root) == ["新名"]
    # 数据随目录迁移
    moved = UserStore(root, "新名").load_profile()
    assert moved.accounts[0].handle == "demo"
    assert UserStore(root, "新名").load_submissions("codeforces", "demo")[1] == 0
    assert not UserStore(root, "旧名").load_profile().accounts


def test_rename_group_conflict_and_missing(tmp_path):
    root = tmp_path / "user"
    create_group(root, "A")
    create_group(root, "B")
    with pytest.raises(ConflictError):
        rename_group(root, "A", "B")
    with pytest.raises(NotFoundError):
        rename_group(root, "不存在", "C")


def test_delete_group_removes_tree(tmp_path):
    root = tmp_path / "user"
    create_group(root, "A")
    create_group(root, "B")
    delete_group(root, "A")
    assert list_groups(root) == ["B"]
    with pytest.raises(NotFoundError):
        delete_group(root, "A")


def test_chinese_group_name_allowed(tmp_path):
    """中文组名正常放行，路径安全。"""
    root = tmp_path / "user"
    name = create_group(root, "算法训练·秋")
    assert name == "算法训练·秋"
    assert (root / name).is_dir()


# ===== secrets（凭据） =====


def test_secrets_roundtrip(tmp_path):
    """凭据写入/读取往返；不同平台与账号隔离。"""
    store = make_store(tmp_path)
    cred = Credentials(cookies={"_uid": "1", "__client_id": "abc"}, headers={})
    store.save_account_secrets("luogu", "100", cred)
    loaded = store.get_account_credentials("luogu", "100")
    assert loaded is not None
    assert loaded.cookies["__client_id"] == "abc"
    assert store.get_account_credentials("luogu", "200") is None
    assert store.get_account_credentials("codeforces", "demo") is None


def test_secrets_corrupt_falls_back_to_empty(tmp_path):
    """secrets.json 损坏按空凭据集处理（不阻断）。"""
    store = make_store(tmp_path)
    store.save_account_secrets("luogu", "100", Credentials(cookies={"_uid": "1"}))
    (tmp_path / "user" / "default" / "secrets.json").write_text("not json", encoding="utf-8")
    assert store.get_account_credentials("luogu", "100") is None


def test_remove_account_cleans_secrets(tmp_path):
    """解绑/换绑（remove_account）同步清理该账号凭据。"""
    store = make_store(tmp_path)
    store.save_account(Account(platform="luogu", handle="100"))
    store.save_account_secrets("luogu", "100", Credentials(cookies={"_uid": "1"}))
    store.remove_account("luogu", "100")
    assert store.get_account_credentials("luogu", "100") is None


def test_remove_account_secrets_idempotent(tmp_path):
    """删除不存在的凭据为空操作；同平台其他账号凭据不受影响。"""
    store = make_store(tmp_path)
    store.save_account_secrets("luogu", "100", Credentials(cookies={"_uid": "1"}))
    store.remove_account_secrets("luogu", "999")
    assert store.get_account_credentials("luogu", "100") is not None
