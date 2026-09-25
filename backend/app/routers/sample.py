"""取样检测接口：维护检测单，覆盖开始检测、判定合格、判定不合格等动作。

必填校验、分页口径、结论/状态映射都取自 app.services.sample，
接口层不再自己维护一份字段或状态清单。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.sample import (
    DEFAULT_PAGE,
    DEFAULT_SIZE,
    ENTRY_LABEL,
    STATUS_ORDER,
    SampleService,
    validate_pagination,
)

router = APIRouter(prefix="/api/sample", tags=["取样检测"])

service = SampleService()


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按检测单号检索"),
    status: str | None = Query(default=None, description="、".join(STATUS_ORDER)),
    page: int = DEFAULT_PAGE,
    size: int = DEFAULT_SIZE,
) -> PageResult[dict]:
    """按检测单号与状态过滤取样检测列表；没有数据时返回空页，不报错。"""
    try:
        validate_pagination(page, size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


# 注意：静态路径必须声明在 /{entry_id} 之前，否则「export」会被当成检测单 id 解析，
# 触发 422 导致导出接口直接报错。
@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出取样检测清单：返回全量数据；没有可导出的记录时带上说明而不是报错。"""
    items, total = service.list_all_entries()
    message = "暂无取样检测数据可导出，请先登记检测单" if total == 0 else f"已导出 {total} 条取样检测记录"
    return {"module": "sample", "total": total, "message": message, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条检测单明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"{ENTRY_LABEL} {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条检测单，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="检测单已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条检测单执行开始检测、判定合格、判定不合格；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
