/**
 * 取样检测模块的统一口径：列表字段、登记必填项、状态序列与判定动作只在这里维护一份。
 * 后端 app/services/sample.py 维护同一套规则，改判定/状态时两边对照修改。
 */

export const ENDPOINT = '/api/sample'

/** 列表、筛选与空数据提示共用的列顺序，与后端 LIST_FIELDS 保持一致 */
export const COLUMNS = [
  '检测单号',
  '取样点位',
  '检测项目',
  '检测值',
  '标准限值',
  '检测结论',
  '检测人员',
  '检测状态',
] as const

/** 登记必填字段：检测单号、取样点位等缺任一项都不能建单 */
export const REQUIRED_FIELDS = ['检测单号', '取样点位', '检测项目'] as const

/** 允许的状态序列，与后端 STATUS_ORDER 一致 */
export const STATUS_ORDER = ['待取样', '检测中', '合格', '不合格'] as const

/** 判定动作到目标状态的映射，合格/不合格写法都从这里取，不再各写一遍 */
export const ACTION_RULES: Record<string, (typeof STATUS_ORDER)[number]> = {
  开始检测: '检测中',
  判定合格: '合格',
  判定不合格: '不合格',
}

/** 列表上可执行的动作按钮，直接由映射表派生 */
export const ACTIONS = Object.keys(ACTION_RULES)

/** 登记前校验必填项：空白输入也算没填，返回缺失字段名 */
export function findMissingFields(values: Record<string, unknown>): string[] {
  return REQUIRED_FIELDS.filter((field) => !String(values[field] ?? '').trim())
}
