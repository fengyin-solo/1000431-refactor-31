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
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
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
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
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
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyText }}</td>
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

import { ACTIONS, COLUMNS, ENDPOINT, REQUIRED_FIELDS } from './rules'

type Row = Record<string, string | number | null>

type ActionResponse = {
  ok: boolean
  message: string
  entry?: Row | null
}

const columns = COLUMNS
const actions = ACTIONS
const stats = [{"label": "待取样检测", "value": 0}, {"label": "检测合格率", "value": 0}, {"label": "不合格批次", "value": 0}]

/** 筛选框只取必填字段，与登记口径一致，不再单独写一份列名 */
const filterFields = [...REQUIRED_FIELDS]
/** 空数据说明：接口返回空页时原样展示，不让人误以为加载失败 */
const emptyText = '暂无取样检测数据，可先登记检测单（检测单号、取样点位、检测项目为必填）'

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  // 后端 /export 为静态路径，已置于 /{id} 之前，导出不会再被当成检测单解析报错
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '检测单登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const payload = (await response.json()) as ActionResponse
    // 动作被业务规则拦下时接口仍返回 200，以 body 中的 ok/message 为准，直接透传后端说明
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
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('检测单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '取样检测列表读取失败'
  }
}

onMounted(reload)
</script>
