<template>
  <section class="page" data-module="sample">
    <header class="page-head">
      <div>
        <h2>取样检测管理</h2>
        <p class="page-desc">维护检测单，围绕检测单号、取样点位、检测项目、检测值做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记检测单</button>
        <button class="btn" type="button" @click="exportRows">导出取样检测清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field.key" class="filter-item">
        <span>{{ field.label }}</span>
        <input v-model="filters[field.key]" :placeholder="`按${field.label}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ displayCell(row[column]) }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ noticeMessage || '暂无取样检测数据，可先登记检测单' }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条取样检测记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/sample'
const EMPTY_TEXT = '未填报'
const columns = ['检测单号', '取样点位', '检测项目', '检测值', '标准限值', '检测结论', '检测人员', '检测状态']
const actions = ['开始检测', '判定合格', '判定不合格']
const stats = [{ label: '待取样检测', value: 0 }, { label: '检测合格率', value: 0 }, { label: '不合格批次', value: 0 }]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = [
  { key: '检测单号', label: '检测单号' },
  { key: '检测状态', label: '检测状态' },
]

function displayCell(value: Row[string]) {
  return value === null || value === undefined || value === '' ? EMPTY_TEXT : value
}

function buildQuery() {
  const params = new URLSearchParams()
  const keyword = filters.value['检测单号']?.trim()
  const status = filters.value['检测状态']?.trim()
  if (keyword) params.set('keyword', keyword)
  if (status) params.set('status', status)
  const query = params.toString()
  return query ? `?${query}` : ''
}

async function readResponseMessage(response: Response, fallback: string) {
  try {
    const payload = await response.json()
    if (typeof payload?.detail === 'string') return payload.detail
    if (typeof payload?.message === 'string') return payload.message
  } catch {
    // 非 JSON 错误沿用兜底说明。
  }
  return fallback
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export${buildQuery()}`, '_blank')
}

function openCreate() {
  errorMessage.value = '检测单登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '取样检测动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '取样检测操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}${buildQuery()}`)
    if (!response.ok) {
      throw new Error(await readResponseMessage(response, '检测单列表读取失败'))
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    noticeMessage.value = payload.message ?? ''
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '取样检测列表读取失败'
  }
}

onMounted(reload)
</script>
