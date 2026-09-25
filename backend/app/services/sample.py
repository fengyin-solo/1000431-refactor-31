"""取样检测业务规则：登记校验、合格判定与结论/状态映射统一收在这里。

登记必填字段、动作到状态的判定写法、状态到「检测结论/检测状态」的展示映射
都只在本文件维护一份；列表接口、详情接口、导出接口与判定动作共用同一套口径，
避免改了一边另外两边不生效。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "sample"
ENTRY_LABEL = "检测单"

# 列表/详情/导出统一返回的字段顺序
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
# 登记时的必填项，缺任意一项都不允许建单
REQUIRED_FIELDS = ["检测单号", "取样点位", "检测项目"]
# 结论列与状态列
CONCLUSION_FIELD = "检测结论"
STATUS_TEXT_FIELD = "检测状态"

# 状态序列与动作到状态的判定写法（合格/不合格都从这里查，不再各写一遍）
STATUS_ORDER = ["待取样", "检测中", "合格", "不合格"]
DEFAULT_STATUS = STATUS_ORDER[0]
ACTION_RULES = {"开始检测": "检测中", "判定合格": "合格", "判定不合格": "不合格"}
# 既有判定动作的异常标记口径，重构保持不变
NEGATIVE_ACTIONS: list[str] = []

# 分页口径
DEFAULT_PAGE = 1
DEFAULT_SIZE = 20
MAX_PAGE_SIZE = 200

# 各状态下的结论说明：未出数据与已判定都有明确文案，避免展示空白或误导
STATUS_CONCLUSIONS = {
    "待取样": "暂无检测数据",
    "检测中": "检测中，待出结论",
    "合格": "合格",
    "不合格": "不合格（检测值超过标准限值）",
}
# 检测值/标准限值无法解析为数值时的说明
NON_NUMERIC_NOTE = "检测值或标准限值不是数值，无法判断是否超限"


class SampleService:
    def _query_rows(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """按检测单号与状态筛选，列表与导出共用，保证两边数据口径一致。"""
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("检测单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        return rows

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = DEFAULT_PAGE,
        size: int = DEFAULT_SIZE,
    ) -> tuple[list[dict[str, Any]], int]:
        validate_pagination(page, size)
        rows = self._query_rows(keyword=keyword, status=status)
        total = len(rows)
        start = max(page - 1, 0) * size
        return [present_entry(row) for row in rows[start:start + size]], total

    def list_all_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """导出专用：不分页返回筛选后的全量数据。"""
        rows = self._query_rows(keyword=keyword, status=status)
        return [present_entry(row) for row in rows], len(rows)

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return present_entry(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = find_missing_fields(values)
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        # 其余登记信息（检测值、标准限值、检测人员等）有值就一并保留
        entry.update({
            field: values.get(field)
            for field in LIST_FIELDS
            if field not in REQUIRED_FIELDS and str(values.get(field) or "").strip()
        })
        entry["status"] = DEFAULT_STATUS
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return present_entry(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"{ENTRY_LABEL} {entry_id} 不存在或已归档"
        target = action_target_status(action)
        if target is None:
            return None, f"动作「{action}」不属于取样检测可执行范围"
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return present_entry(entry), f"{ENTRY_LABEL}已{action}"


# ---- 共用的校验与映射实现：接口层、其他模块（如需要）都从这里取 ----

def find_missing_fields(values: dict[str, Any]) -> list[str]:
    """登记必填校验：检测单号、取样点位等缺哪个就回哪个，空白字符也算没填。"""
    return [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]


def validate_pagination(page: int, size: int) -> None:
    """分页参数校验：页码至少为 1；每页至少 1 条、最多 MAX_PAGE_SIZE 条。"""
    if page < 1:
        raise ValueError("页码至少为 1，请检查分页参数")
    if size < 1:
        raise ValueError("每页条数至少为 1 条")
    if size > MAX_PAGE_SIZE:
        raise ValueError(f"每页最多 {MAX_PAGE_SIZE} 条，请缩小分页范围或改用导出")


def action_target_status(action: str) -> str | None:
    """动作到目标状态的判定写法：合格/不合格统一查 ACTION_RULES。"""
    return ACTION_RULES.get(action)


def _as_number(value: Any) -> float | None:
    """把检测值/标准限值解析成数值；空值与非数值返回 None，由调用方给说明。"""
    if value is None or not str(value).strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def exceeds_limit(value: Any, limit: Any) -> bool | None:
    """检测值是否超过标准限值；无法比较时返回 None 而不是误判。"""
    measured = _as_number(value)
    threshold = _as_number(limit)
    if measured is None or threshold is None:
        return None
    return measured > threshold


def conclusion_for(entry: dict[str, Any]) -> str:
    """状态到检测结论的统一映射，列表、详情、导出共用。

    - 待取样：说明暂无检测数据，不展示空白；
    - 检测中：说明结论待出；
    - 合格：给合格结论；
    - 不合格：给不合格结论；检测值能证明超限才带「超限」说明，
      值缺失或不是数值时如实说明，不编造超限结论。
    """
    status = str(entry.get("status") or DEFAULT_STATUS)
    conclusion = STATUS_CONCLUSIONS.get(status, status)
    if status == "不合格":
        over_limit = exceeds_limit(entry.get("检测值"), entry.get("标准限值"))
        if over_limit is False:
            conclusion = "不合格（检测值未超过标准限值，以人工判定为准）"
        elif over_limit is None:
            conclusion = f"不合格（{NON_NUMERIC_NOTE}，以人工判定为准）"
    return conclusion


def present_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """给存储记录补上统一口径的展示字段：检测结论与检测状态都由状态派生。"""
    presented = dict(entry)
    presented[CONCLUSION_FIELD] = conclusion_for(entry)
    presented[STATUS_TEXT_FIELD] = str(entry.get("status") or DEFAULT_STATUS)
    return presented
