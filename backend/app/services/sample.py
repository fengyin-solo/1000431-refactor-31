"""取样检测业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "sample"
ID_FIELD = "检测单号"
REQUIRED_FIELDS = ["检测单号", "取样点位", "检测项目"]
LIST_FIELDS = [
    "检测单号",
    "取样点位",
    "检测项目",
    "检测值",
    "标准限值",
    "检测结论",
    "检测人员",
    "检测状态",
]

PENDING_STATUS = "待取样"
TESTING_STATUS = "检测中"
QUALIFIED_STATUS = "合格"
UNQUALIFIED_STATUS = "不合格"
STATUS_ORDER = [PENDING_STATUS, TESTING_STATUS, QUALIFIED_STATUS, UNQUALIFIED_STATUS]
JUDGED_STATUSES = {QUALIFIED_STATUS, UNQUALIFIED_STATUS}
ACTION_RULES = {
    "开始检测": TESTING_STATUS,
    "判定合格": QUALIFIED_STATUS,
    "判定不合格": UNQUALIFIED_STATUS,
}
NEGATIVE_ACTIONS: list[str] = []

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 200
EXPORT_LIMIT = 10_000
EMPTY_TEXT = "未填报"
UNJUDGED_CONCLUSION = "未判定"


def clean_text(value: Any) -> str:
    """统一把 0 等已有值保留下来，只把空值和空白字符串视为空。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def validate_required_fields(
    values: dict[str, Any],
    required_fields: list[str] | None = None,
) -> list[str]:
    """登记校验的唯一入口，按字段顺序返回缺失项。"""
    fields = required_fields or REQUIRED_FIELDS
    return [field for field in fields if not clean_text(values.get(field))]


def missing_required_message(missing_fields: list[str]) -> str:
    return f"缺少必填字段：{'、'.join(missing_fields)}"


def validate_pagination(page: int, size: int, *, max_size: int = MAX_PAGE_SIZE) -> tuple[int, int]:
    """分页口径统一在这里说明，避免路由和 service 各自兜底。"""
    try:
        normalized_page = int(page)
        normalized_size = int(size)
    except (TypeError, ValueError):
        raise ValueError("页码和每页条数必须是整数") from None

    if normalized_page < 1:
        raise ValueError("页码必须大于 0，请从第 1 页开始查询")
    if normalized_size < 1:
        raise ValueError("每页条数必须大于 0")
    if normalized_size > max_size:
        raise ValueError(f"每页最多 {max_size} 条，请缩小分页范围")
    return normalized_page, normalized_size


def normalize_filter_value(value: str | None) -> str | None:
    keyword = clean_text(value)
    return keyword or None


def conclusion_for_status(status: str) -> str:
    """人工判定只认动作映射出的状态，未出结论时给明确说明。"""
    if status in JUDGED_STATUSES:
        return status
    return UNJUDGED_CONCLUSION


def serialize_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """列表、详情、动作结果和导出共用同一份展示字段。"""
    status = clean_text(raw.get("status")) or PENDING_STATUS
    if status not in STATUS_ORDER:
        status = PENDING_STATUS

    serialized: dict[str, Any] = {"id": int(raw.get("id", 0))}
    for field in LIST_FIELDS:
        serialized[field] = clean_text(raw.get(field)) or EMPTY_TEXT

    serialized["检测结论"] = conclusion_for_status(status)
    serialized["检测状态"] = status
    serialized["status"] = status
    serialized["pending"] = bool(raw.get("pending", status not in JUDGED_STATUSES))
    serialized["abnormal"] = bool(raw.get("abnormal", False))
    return serialized


def empty_list_message(total: int, page: int, size: int) -> str | None:
    if total:
        total_pages = (total + size - 1) // size
        if page > total_pages:
            return f"第 {page} 页暂无数据，当前共 {total} 条，请返回前 {total_pages} 页查看"
        return None
    return "当前筛选条件下暂无取样检测记录"


def export_message(total: int, limit: int = EXPORT_LIMIT) -> str:
    if not total:
        return "当前筛选条件下暂无可导出的取样检测记录"
    if total > limit:
        return f"符合条件的记录共 {total} 条，超过单次导出上限 {limit} 条，请增加筛选条件后重试"
    return "取样检测清单导出成功"


class SampleService:
    def filtered_entries(self, *, keyword: str | None = None, status: str | None) -> list[dict[str, Any]]:
        normalized_keyword = normalize_filter_value(keyword)
        normalized_status = normalize_filter_value(status)

        rows = store.rows(MODULE)
        if normalized_keyword:
            rows = [row for row in rows if normalized_keyword in clean_text(row.get(ID_FIELD))]
        if normalized_status:
            rows = [row for row in rows if row.get("status") == normalized_status]
        return rows

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = DEFAULT_PAGE_SIZE,
        max_size: int = MAX_PAGE_SIZE,
    ) -> tuple[list[dict[str, Any]], int]:
        page, size = validate_pagination(page, size, max_size=max_size)
        rows = self.filtered_entries(keyword=keyword, status=status)
        total = len(rows)
        start = (page - 1) * size
        return [serialize_entry(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return serialize_entry(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = validate_required_fields(values)
        if missing:
            return None, missing

        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: clean_text(values.get(field)) for field in REQUIRED_FIELDS})
        entry["status"] = PENDING_STATUS
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return serialize_entry(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检测单 {entry_id} 不存在或已归档"

        normalized_action = clean_text(action)
        if normalized_action not in ACTION_RULES:
            return None, f"动作「{normalized_action}」不属于取样检测可执行范围"

        target = ACTION_RULES[normalized_action]
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = normalized_action in NEGATIVE_ACTIONS
        return serialize_entry(entry), f"检测单已{normalized_action}"
