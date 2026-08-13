"""activity HTTP 边界：只做参数校验与转发，平台无关。

不写业务逻辑、不宽泛 try/except，异常统一交由全局异常处理器。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from modules.activity.schemas import (
    BindIn,
    BoundAccountOut,
    OverviewOut,
    PlatformsOut,
    SubmissionsOut,
    SyncIn,
    VerifyIn,
    VerifyOut,
)
from services.activity.service import ActivityService, get_activity_service

router = APIRouter(prefix="/api/activity", tags=["activity"])

ServiceDep = Annotated[ActivityService, Depends(get_activity_service)]


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
