"""main.lifespan 启动行为测试：启动时自动同步的开关接线。

不启动真实服务：直接驱动 lifespan 上下文，模板/打印册等无关服务打桩，
只验证 activity 服务的 sync_all_groups() 是否按配置被触发。
"""

import main as main_mod
from core.config import Settings


class _FakeActivityService:
    def __init__(self) -> None:
        self.sync_all_groups_calls: list[None] = []

    async def sync_all_groups(self) -> None:
        self.sync_all_groups_calls.append(None)

    async def aclose(self) -> None:
        pass


def _patch_infra(monkeypatch, settings: Settings, activity):
    """打桩 lifespan 内的无关重活（模板索引/打印册/导入导出/文件监听）。"""
    monkeypatch.setattr(main_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(main_mod, "init_activity_service", lambda s: activity)

    class _Noop:
        def diagnostics(self):
            return []

    monkeypatch.setattr(main_mod, "init_template_service", lambda s: _Noop())
    monkeypatch.setattr(main_mod, "init_print_book_service", lambda s, t: None)
    monkeypatch.setattr(main_mod, "init_transfer_service", lambda s, t: None)


async def test_startup_triggers_sync_all_accounts(monkeypatch, tmp_path):
    """默认开启：lifespan 就绪后对所有用户组全部账号触发一次同步（sync_all_groups()）。"""
    settings = Settings(
        user_data_dir=tmp_path / "user",
        watch_enabled=False,
        activity_sync_on_startup=True,
    )
    activity = _FakeActivityService()
    _patch_infra(monkeypatch, settings, activity)

    app = main_mod.create_app()
    async with main_mod.lifespan(app):
        pass

    assert activity.sync_all_groups_calls == [None]  # None = 全部组全部账号


async def test_startup_sync_disabled_by_config(monkeypatch, tmp_path):
    """activity_sync_on_startup=false 时启动不触发同步。"""
    settings = Settings(
        user_data_dir=tmp_path / "user",
        watch_enabled=False,
        activity_sync_on_startup=False,
    )
    activity = _FakeActivityService()
    _patch_infra(monkeypatch, settings, activity)

    app = main_mod.create_app()
    async with main_mod.lifespan(app):
        pass

    assert activity.sync_all_groups_calls == []
