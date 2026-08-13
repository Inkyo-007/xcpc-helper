"""data/user/<userid>/ 读写层：原子写、锁、JSONL 去重合并。

设计原则（对齐 conventions.md 与 printbook store）：
- 写操作一律临时文件 + os.replace 原子替换；
- 同资源并发写用 RLock 串行化；
- 账号名经 common.validation.validate_name 校验，杜绝路径穿越；
- JSONL 读入合并去重后整体原子替换（见 activity.md §3.3）；
- 单行损坏只跳过不阻断（"诊断不阻断"哲学）。
"""

import json
import os
import tempfile
import threading
from pathlib import Path

from pydantic import ValidationError

from common.validation import validate_name
from modules.activity.models import DEFAULT_USER_ID, Account, Profile, Submission

PROFILE_FILE = "profile.json"
SUBMISSIONS_DIR = Path("activity") / "submissions"


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


class UserStore:
    """单用户组数据目录读写。第一期固定 DEFAULT_USER_ID。"""

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
        """从档案移除账号并删除其提交数据（解绑）。"""
        with self._lock:
            profile = self.load_profile()
            profile.accounts = [
                acc
                for acc in profile.accounts
                if not (acc.platform == platform and acc.handle == handle)
            ]
            self.save_profile(profile)
            self._submissions_file(platform, handle).unlink(missing_ok=True)

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
