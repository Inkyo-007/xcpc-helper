"""data/user/<userid>/ 读写层：原子写、锁、JSONL 去重合并、用户组目录管理。

设计原则（对齐 conventions.md 与 printbook store）：
- 写操作一律临时文件 + os.replace 原子替换；
- 同资源并发写用 RLock 串行化；
- 账号名经 common.validation.validate_name 校验，杜绝路径穿越；
- JSONL 读入合并去重后整体原子替换（见 activity.md §3.3）；
- 单行损坏只跳过不阻断（"诊断不阻断"哲学）；
- 用户组 = data/user/<user_id>/ 目录（目录名即组名，中文放行），
  创建/重命名同步目录名，删除为物理删除（前端明确提示不可找回）。
"""

import json
import os
import shutil
import tempfile
import threading
from pathlib import Path

from pydantic import ValidationError

from adapters.base import Credentials
from common.validation import validate_name
from core.exceptions import ConflictError, NotFoundError
from modules.activity.models import (
    DEFAULT_USER_ID,
    Account,
    Profile,
    Secrets,
    Submission,
)

PROFILE_FILE = "profile.json"
SECRETS_FILE = "secrets.json"  # 凭据（gitignore，仅存本机）
SUBMISSIONS_DIR = Path("activity") / "submissions"

# 格式样例目录（入 git 的 example 样例，不作为用户组参与管理）
EXAMPLE_GROUP = "example"


def _atomic_write(path: Path, text: str) -> None:
    """原子写入文本文件：先写同目录临时文件，再 os.replace 覆盖目标。"""
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# ===== 用户组目录管理（root 层） =====


def list_groups(root: Path) -> list[str]:
    """data/user/ 下全部用户组目录名（升序；跳过隐藏目录与 example 样例）。"""
    if not root.is_dir():
        return []
    return sorted(
        (
            p.name
            for p in root.iterdir()
            if p.is_dir()
            and not p.name.startswith(".")
            and p.name != EXAMPLE_GROUP
        ),
        key=str.lower,
    )


def create_group(root: Path, name: str) -> str:
    """新建用户组目录 + 初始档案（信息卡 ID 初始为目录名），返回规范化组名。"""
    name = validate_name(name, "用户组")
    group_dir = root / name
    if group_dir.exists():
        raise ConflictError(f"用户组已存在: {name}")
    root.mkdir(parents=True, exist_ok=True)
    group_dir.mkdir()
    UserStore(root, name).save_profile(Profile(id=name))
    return name


def rename_group(root: Path, name: str, new_name: str) -> str:
    """用户组目录改名（数据随目录迁移，归属不变），返回新组名。"""
    name = validate_name(name, "用户组")
    new_name = validate_name(new_name, "用户组")
    src = root / name
    if not src.is_dir():
        raise NotFoundError(f"用户组不存在: {name}")
    if new_name == name:
        return name
    dst = root / new_name
    if dst.exists():
        raise ConflictError(f"用户组已存在: {new_name}")
    os.rename(src, dst)
    return new_name


def delete_group(root: Path, name: str) -> None:
    """物理删除用户组目录（含账号绑定、训练数据与信息卡，不可找回）。"""
    name = validate_name(name, "用户组")
    group_dir = root / name
    if not group_dir.is_dir():
        raise NotFoundError(f"用户组不存在: {name}")
    shutil.rmtree(group_dir)


class UserStore:
    """单用户组数据目录读写。"""

    def __init__(self, root: Path, user_id: str = DEFAULT_USER_ID) -> None:
        self._dir = root / user_id
        self._lock = threading.RLock()

    # ===== profile =====

    def load_profile(self) -> Profile:
        """读取 profile.json；不存在返回空档案（id 取 user_id）。"""
        profile_file = self._dir / PROFILE_FILE
        if not profile_file.is_file():
            return Profile(id=self._dir.name)
        try:
            raw = json.loads(profile_file.read_text(encoding="utf-8"))
            return Profile.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError):
            # 档案损坏：按空档案处理，不阻断（用户可重新绑定）
            return Profile(id=self._dir.name)

    def save_profile(self, profile: Profile) -> None:
        """原子写入 profile.json。"""
        with self._lock:
            self._dir.mkdir(parents=True, exist_ok=True)
            text = json.dumps(
                profile.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            )
            _atomic_write(self._dir / PROFILE_FILE, text)

    def save_account(self, account: Account) -> None:
        """更新单个账号的绑定信息（新增/换绑/同步游标推进）。"""
        with self._lock:
            profile = self.load_profile()
            for i, acc in enumerate(profile.accounts):
                if acc.platform == account.platform and acc.handle == account.handle:
                    profile.accounts[i] = account
                    break
            else:
                profile.accounts.append(account)
            self.save_profile(profile)

    def remove_account(self, platform: str, handle: str) -> None:
        """从档案移除账号并删除其提交数据与凭据（解绑）。"""
        with self._lock:
            profile = self.load_profile()
            profile.accounts = [
                acc
                for acc in profile.accounts
                if not (acc.platform == platform and acc.handle == handle)
            ]
            self.save_profile(profile)
            self._submissions_file(platform, handle).unlink(missing_ok=True)
            self.remove_account_secrets(platform, handle)

    # ===== secrets（凭据，gitignore 仅存本机） =====

    def load_secrets(self) -> Secrets:
        """读取 secrets.json；不存在或损坏返回空凭据集（不阻断）。"""
        secrets_file = self._dir / SECRETS_FILE
        if not secrets_file.is_file():
            return Secrets()
        try:
            raw = json.loads(secrets_file.read_text(encoding="utf-8"))
            return Secrets.model_validate(raw)
        except (OSError, json.JSONDecodeError, ValidationError):
            return Secrets()

    def get_account_credentials(
        self, platform: str, handle: str
    ) -> Credentials | None:
        """读取单个账号凭据（同步用）；无则 None。"""
        return self.load_secrets().platforms.get(platform, {}).get(handle)

    def save_account_secrets(
        self, platform: str, handle: str, credentials: Credentials
    ) -> None:
        """写入单个账号凭据（绑定/换绑/凭据刷新），原子写。"""
        handle = validate_name(handle, "账号")
        with self._lock:
            secrets = self.load_secrets()
            secrets.platforms.setdefault(platform, {})[handle] = credentials
            self._save_secrets(secrets)

    def remove_account_secrets(self, platform: str, handle: str) -> None:
        """删除单个账号凭据（解绑/换绑清理）；不存在为空操作。"""
        with self._lock:
            secrets = self.load_secrets()
            handles = secrets.platforms.get(platform)
            if not handles or handle not in handles:
                return
            handles.pop(handle)
            if not handles:
                secrets.platforms.pop(platform)
            self._save_secrets(secrets)

    def _save_secrets(self, secrets: Secrets) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        text = json.dumps(
            secrets.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        _atomic_write(self._dir / SECRETS_FILE, text)

    # ===== submissions =====

    def _submissions_file(self, platform: str, handle: str) -> Path:
        handle = validate_name(handle, "账号")
        return self._dir / SUBMISSIONS_DIR / f"{platform}_{handle}.jsonl"

    def load_submissions(self, platform: str, handle: str) -> tuple[list[Submission], int]:
        """读取账号提交（按行解析）；返回 (提交列表, 损坏行数)。"""
        path = self._submissions_file(platform, handle)
        if not path.is_file():
            return [], 0
        items: list[Submission] = []
        skipped = 0
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return [], 0
        for line in lines:
            if not line.strip():
                continue
            try:
                items.append(Submission.model_validate_json(line))
            except (json.JSONDecodeError, ValidationError):
                skipped += 1
        return items, skipped

    def merge_submissions(
        self, platform: str, handle: str, incoming: list[Submission]
    ) -> int:
        """按 submission_id 去重合并后整体原子替换，返回新增条数。

        已存在的数据以磁盘为准（读入合并），新增按时间升序追加，
        写回时按 submitted_at 升序稳定排序，保持 JSONL 可读。
        """
        with self._lock:
            existing, _skipped = self.load_submissions(platform, handle)
            by_id = {s.submission_id: s for s in existing}
            added = 0
            for s in incoming:
                if s.submission_id not in by_id:
                    by_id[s.submission_id] = s
                    added += 1
            merged = sorted(by_id.values(), key=lambda s: s.submitted_at)
            path = self._submissions_file(platform, handle)
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = "".join(
                s.model_dump_json() + "\n" for s in merged
            )
            _atomic_write(path, lines)
            return added
