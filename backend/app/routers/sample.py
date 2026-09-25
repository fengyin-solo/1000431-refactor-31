"""取样检测接口：维护检测单，覆盖开始检测、判定合格、判定不合格等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services import sample as sample_rules
from app.services.sample import (
    EXPORT_LIMIT,
    MAX_PAGE_SIZE,
    SampleService,
    empty_list_message,
    export_message,
    missing_required_message,
)

router = APIRouter(prefix="/api/sample", tags=["取样检测"])

service = SampleService()

LIST_FIELDS = sample_rules.LIST_FIELDS
STATUSES = sample_rules.STATUS_ORDER


class SamplePageResult(PageResult[dict]):
    message: str | None = None


def list_result(
    *,
    keyword: str | None,
    status: str | None,
    page: int,
    size: int,
    max_size: int = MAX_PAGE_SIZE,
) -> SamplePageResult:
    try:
        items, total = service.list_entries(
            keyword=keyword,
            status=status,
            page=page,
            size=size,
            max_size=max_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    normalized_page = max(page, 1)
    return SamplePageResult(
        items=items,
        total=total,
        page=normalized_page,
        size=size,
        message=empty_list_message(total, normalized_page, size),
    )


@router.get("", response_model=SamplePageResult)
def list_entries(
    keyword: str | None = Query(default=None, description="按检测单号检索"),
    status: str | None = Query(default=None, description="待取样、检测中、合格、不合格"),
    page: int = 1,
    size: int = 20,
) -> SamplePageResult:
    """按检测单号与状态过滤取样检测列表；没有数据时返回空页，不报错。"""
    return list_result(keyword=keyword, status=status, page=page, size=size)


@router.get("/export")
def export_entries(
    keyword: str | None = Query(default=None, description="按检测单号检索"),
    status: str | None = Query(default=None, description="待取样、检测中、合格、不合格"),
) -> dict[str, Any]:
    """导出当前筛选条件下不超过上限的取样检测数据；空结果也返回明确说明。"""
    try:
        total = len(service.filtered_entries(keyword=keyword, status=status))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if total > EXPORT_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=export_message(total, EXPORT_LIMIT),
        )

    result = list_result(
        keyword=keyword,
        status=status,
        page=1,
        size=max(total, 1),
        max_size=EXPORT_LIMIT,
    )
    return {
        "module": "sample",
        "total": result.total,
        "message": export_message(result.total, EXPORT_LIMIT),
        "items": result.items,
    }


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条检测单明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检测单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条检测单，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=missing_required_message(missing))
    return ActionResult(ok=True, message="检测单已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条检测单执行开始检测、判定合格、判定不合格；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
