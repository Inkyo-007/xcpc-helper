"""activity HTTP 边界：只做参数校验与转发，平台无关。

不写业务逻辑、不宽泛 try/except，异常统一交由全局异常处理器。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from modules.activity.schemas import (
    BindIn,
    BoundAccountOut,
    BrowserLoginStatusOut,
    GroupCreateIn,
    GroupOut,
    GroupRenameIn,
    GroupsOut,
    OverviewOut,
    PlatformsOut,
    ProfileOut,
    ProfileUpdateIn,
    RefineConfigIn,
    RefineStatusOut,
    SubmissionsOut,
    SyncIn,
    UpdateCredentialsIn,
    VerifyIn,
    VerifyOut,
)
from services.activity.service import ActivityService, get_activity_service

router = APIRouter(prefix="/api/activity", tags=["activity"])

ServiceDep = Annotated[ActivityService, Depends(get_activity_service)]


# ===== 用户组与信息卡 =====


@router.get("/groups", response_model=GroupsOut)
async def get_groups(service: ServiceDep) -> GroupsOut:
    return service.groups()


@router.post("/groups", response_model=GroupOut, status_code=201)
async def create_group(payload: GroupCreateIn, service: ServiceDep) -> GroupOut:
    return service.create_group(payload)


@router.patch("/groups/{name}", response_model=GroupsOut)
async def rename_group(
    name: str, payload: GroupRenameIn, service: ServiceDep
) -> GroupsOut:
    return service.rename_group(name, payload)


@router.delete("/groups/{name}", status_code=204)
async def delete_group(name: str, service: ServiceDep) -> None:
    service.delete_group(name)


@router.post("/current-group", response_model=GroupOut)
async def switch_group(payload: GroupCreateIn, service: ServiceDep) -> GroupOut:
    return service.switch_group(payload.name)


@router.get("/profile", response_model=ProfileOut)
async def get_profile(service: ServiceDep) -> ProfileOut:
    return service.current_profile()


@router.patch("/profile", response_model=ProfileOut)
async def update_profile(
    payload: ProfileUpdateIn, service: ServiceDep
) -> ProfileOut:
    return service.update_profile(payload)


@router.get("/platforms", response_model=PlatformsOut)
async def get_platforms(service: ServiceDep) -> PlatformsOut:
    return service.platforms()


@router.post("/accounts/verify", response_model=VerifyOut)
async def verify_account(payload: VerifyIn, service: ServiceDep) -> VerifyOut:
    return await service.verify(payload)


@router.post("/accounts", response_model=BoundAccountOut, status_code=201)
async def bind_account(payload: BindIn, service: ServiceDep) -> BoundAccountOut:
    return await service.bind(payload)


@router.delete("/accounts/{platform}/{handle}", status_code=204)
async def unbind_account(
    platform: str, handle: str, service: ServiceDep
) -> None:
    service.unbind(platform, handle)


@router.put("/accounts/{platform}/{handle}/credentials", response_model=BoundAccountOut)
async def update_account_credentials(
    platform: str,
    handle: str,
    service: ServiceDep,
    payload: UpdateCredentialsIn | None = None,
) -> BoundAccountOut:
    from adapters.base import Credentials

    credentials = (
        Credentials.model_validate(payload.credentials)
        if payload is not None and payload.credentials
        else None
    )
    return await service.update_credentials(platform, handle, credentials)


# ===== 浏览器一键登录（cookie 平台） =====


@router.post("/platforms/{platform}/browser-login", status_code=202)
async def start_browser_login(platform: str, service: ServiceDep) -> None:
    # 立即返回；登录会话后台执行，前端轮询 browser-login/status
    await service.start_browser_login(platform)


@router.get(
    "/platforms/{platform}/browser-login/status",
    response_model=BrowserLoginStatusOut,
)
async def get_browser_login_status(
    platform: str, service: ServiceDep
) -> BrowserLoginStatusOut:
    return service.browser_login_status(platform)


# ===== 精细化同步（REFINE_VERDICT 能力平台） =====


@router.post("/accounts/{platform}/{handle}/refine", status_code=202)
async def start_refine(platform: str, handle: str, service: ServiceDep) -> None:
    # 立即返回；精化后台执行，前端轮询 GET refine
    service.start_refine(platform, handle)


@router.delete("/accounts/{platform}/{handle}/refine", status_code=204)
async def stop_refine(platform: str, handle: str, service: ServiceDep) -> None:
    service.stop_refine(platform, handle)


@router.get("/accounts/{platform}/{handle}/refine", response_model=RefineStatusOut)
async def get_refine_status(
    platform: str, handle: str, service: ServiceDep
) -> RefineStatusOut:
    return service.refine_status(platform, handle)


@router.patch("/accounts/{platform}/{handle}", response_model=RefineStatusOut)
async def update_account_config(
    platform: str, handle: str, payload: RefineConfigIn, service: ServiceDep
) -> RefineStatusOut:
    return service.set_refine_auto(platform, handle, payload.refineAuto)


@router.get("/overview", response_model=OverviewOut)
async def get_overview(
    service: ServiceDep,
    platform: Annotated[str | None, Query()] = None,
) -> OverviewOut:
    return service.overview(platform)


@router.get("/submissions", response_model=SubmissionsOut)
async def get_submissions(
    service: ServiceDep,
    date: Annotated[str | None, Query()] = None,
    platform: Annotated[str | None, Query()] = None,
) -> SubmissionsOut:
    return service.submissions(date=date, platform=platform)


@router.post("/sync", status_code=202)
async def trigger_sync(
    service: ServiceDep,
    payload: SyncIn | None = None,
) -> None:
    # 立即返回；同步后台执行，前端轮询 /sync/status
    await service.sync(payload.platform if payload else None)


@router.get("/sync/status", response_model=list[BoundAccountOut])
async def get_sync_status(service: ServiceDep) -> list[BoundAccountOut]:
    return service.sync_status()
