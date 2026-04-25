<template>
  <div>
    <!-- Key Metric Cards -->
    <n-grid :cols="metricGridCols" :x-gap="16" :y-gap="16" style="margin-bottom: 24px;">
      <n-gi>
        <n-card class="metric-card">
          <div class="metric-value">{{ stats.total_queries || 0 }}</div>
          <div class="metric-label">Total Queries</div>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card class="metric-card">
          <div class="metric-value">{{ stats.avg_response_time_ms?.toFixed(0) || 0 }}</div>
          <div class="metric-label">Avg Response Time (ms)</div>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card class="metric-card">
          <div class="metric-value">{{ stats.avg_accuracy != null ? (stats.avg_accuracy * 100).toFixed(1) + '%' : '0%' }}</div>
          <div class="metric-label">Avg Classification Accuracy</div>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- Charts Row -->
    <n-grid :cols="chartGridCols" :x-gap="16" :y-gap="16" style="margin-bottom: 24px;">
      <!-- Intent Distribution -->
      <n-gi>
        <n-card title="Intent Distribution" style="height: 300px; display: flex; flex-direction: column;">
          <template #header-extra>
            <span style="font-size: 12px; color: #999;">Last 7 days</span>
          </template>
          <div style="flex: 1; overflow: auto;">
            <div v-if="distribution.length === 0" style="text-align: center; color: #999; padding: 40px;">
              No data available
            </div>
            <div v-else class="chart-container">
              <div v-for="item in distribution" :key="item.intent" class="distribution-bar">
                <span class="dist-label">{{ item.intent }}</span>
                <div class="bar-wrapper">
                  <div class="bar" :style="{ width: getBarWidth(item.count) + '%' }"></div>
                </div>
                <span class="dist-count">{{ item.count }}</span>
              </div>
            </div>
          </div>
        </n-card>
      </n-gi>

      <!-- Top Documents -->
      <n-gi>
        <n-card title="Top Documents" style="height: 300px; display: flex; flex-direction: column;">
          <n-data-table
            :columns="topDocColumns"
            :data="topDocuments"
            :pagination="false"
            :loading="loadingDocs"
            size="small"
            :max-height="160"
            :scroll-x="300"
          />
        </n-card>
      </n-gi>
    </n-grid>

    <!-- Query History -->
    <n-card>
      <template #header>
        <n-space vertical justify="space-between" align="stretch">
          <span>Query History</span>
          <n-space :vertical="isMobile" style="gap: 8px;">
            <n-input v-model:value="searchQuery" placeholder="Search..." clearable :style="isMobile ? 'width: 100%;' : 'width: 200px;'" @keyup.enter="loadQueries" />
            <n-button @click="exportCSV" :style="isMobile ? 'width: 100%;' : ''">Export CSV</n-button>
          </n-space>
        </n-space>
      </template>

      <n-data-table
        :columns="queryColumns"
        :data="queries"
        :pagination="pagination"
        :loading="loading"
        :row-key="(row: any) => row.id"
        remote
        :scroll-x="800"
        @update:page="handlePageChange"
      />
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, h } from 'vue'
import {
  NGrid, NGi, NCard, NDataTable, NSpace, NButton, NInput, NTag,
  DataTableColumns, useMessage, NSelect, NPopover
} from 'naive-ui'
import api from '@/api'
import type { AnalyticsStats, IntentDistribution, TopDocument, QueryLog, IntentSpaceResponse } from '@/types'

const message = useMessage()
const isMobile = ref(window.innerWidth < 600)
const isTablet = ref(window.innerWidth >= 600 && window.innerWidth < 960)

const metricGridCols = computed(() => {
  if (isMobile.value) return 1
  if (isTablet.value) return 2
  return 3
})

const chartGridCols = computed(() => {
  if (isMobile.value || isTablet.value) return 1
  return 2
})

window.addEventListener('resize', () => {
  isMobile.value = window.innerWidth < 600
  isTablet.value = window.innerWidth >= 600 && window.innerWidth < 960
})

const stats = ref<AnalyticsStats>({ total_queries: 0, avg_response_time_ms: 0, avg_accuracy: null })
const distribution = ref<IntentDistribution[]>([])
const topDocuments = ref<TopDocument[]>([])
const queries = ref<QueryLog[]>([])
const intentSpaces = ref<IntentSpaceResponse[]>([])
const loading = ref(false)
const loadingDocs = ref(false)
const searchQuery = ref('')
const feedbackUpdating = ref(false)

const intentOptions = computed(() =>
  intentSpaces.value.map(i => ({ label: i.name, value: i.id }))
)

const pagination = reactive({ page: 1, pageSize: 20, itemCount: 0 })

// Reset to page 1 when search changes
watch(searchQuery, () => {
  pagination.page = 1
  loadQueries()
})

const topDocColumns: DataTableColumns<TopDocument> = [
  { title: 'Document', key: 'name', width: 150, ellipsis: true },
  { title: 'Hits', key: 'hit_count', width: 60 },
  { title: 'Intent', key: 'intent_space', width: 100 }
]

const queryColumns: DataTableColumns<QueryLog> = [
  { title: 'Time', key: 'timestamp', width: 160, render: (row) => new Date(row.timestamp).toLocaleString() },
  { title: 'Source', key: 'source', width: 100 },
  { title: 'User', key: 'user_id', width: 120, ellipsis: true },
  { title: 'Query', key: 'query_text', width: 150, ellipsis: true },
  { title: 'Intent', key: 'intent', width: 100 },
  { title: 'Confidence', key: 'confidence', width: 100, render: (row) => row.confidence?.toFixed(2) || '-' },
  { title: 'Time (ms)', key: 'response_time_ms', width: 100 },
  {
    title: 'Feedback',
    key: 'user_feedback',
    width: 200,
    render: (row) => {
      if (row.user_feedback) {
        const type = row.user_feedback === 'correct' ? 'success' : 'error'
        const label = row.user_feedback === 'correct' ? '✓ Correct' : '✗ Wrong'
        return h(NTag, { type, size: 'small' }, { default: () => label })
      }
      // No feedback yet — show inline feedback controls
      return h(NPopover, { trigger: 'click', placement: 'left' }, {
        trigger: () => h(NButton, { size: 'tiny', dashed: true }, { default: () => 'Set' }),
        default: () => h('div', { style: 'display: flex; flex-direction: column; gap: 8px; min-width: 160px;' }, [
          h(NSelect, {
            size: 'small',
            placeholder: 'Feedback',
            options: [
              { label: '✓ Correct', value: 'correct' },
              { label: '✗ Wrong', value: 'wrong' }
            ],
            onUpdateValue: async (feedback: string) => {
              if (feedback === 'correct') {
                await submitFeedback(row.id, 'correct')
              } else if (feedback === 'wrong') {
                ;(row as any)._showIntentSelector = true
              }
            }
          }),
          (row as any)._showIntentSelector ? h(NSelect, {
            size: 'small',
            placeholder: 'Select correct intent',
            options: intentOptions.value,
            onUpdateValue: async (id: number) => {
              await submitFeedback(row.id, 'wrong', id)
              ;(row as any)._showIntentSelector = false
            }
          }) : null
        ])
      })
    }
  }
]

function getBarWidth(count: number): number {
  const max = Math.max(...distribution.value.map(d => d.count))
  return max > 0 ? (count / max) * 100 : 0
}

async function loadStats() {
  try {
    const response = await api.get('/analytics/stats')
    stats.value = response.data
  } catch (e) {
    console.error('Failed to load stats:', e)
  }
}

async function loadDistribution() {
  try {
    const response = await api.get('/analytics/intent-distribution')
    distribution.value = response.data.distribution
  } catch (e) {
    console.error('Failed to load distribution:', e)
  }
}

async function loadTopDocuments() {
  loadingDocs.value = true
  try {
    const response = await api.get('/analytics/top-documents')
    topDocuments.value = response.data.documents
  } catch (e) {
    console.error('Failed to load top documents:', e)
  } finally {
    loadingDocs.value = false
  }
}

async function loadQueries() {
  loading.value = true
  try {
    const params: any = { page: pagination.page, page_size: pagination.pageSize }
    if (searchQuery.value) params.search = searchQuery.value

    const response = await api.get('/analytics/queries', { params })
    queries.value = response.data.items
    pagination.itemCount = response.data.total
  } catch (e) {
    console.error('Failed to load queries:', e)
  } finally {
    loading.value = false
  }
}

async function loadIntentSpaces() {
  try {
    const response = await api.get('/intents')
    intentSpaces.value = response.data.data
  } catch (e) {
    console.error('Failed to load intent spaces:', e)
  }
}

async function submitFeedback(queryId: number, feedback: 'correct' | 'wrong', correctedIntentId?: number) {
  feedbackUpdating.value = true
  try {
    await api.patch(`/analytics/queries/${queryId}/feedback`, {
      feedback,
      corrected_intent_id: correctedIntentId
    })
    message.success('Feedback saved')
    await loadQueries()
    await loadStats()
  } catch (e) {
    message.error('Failed to save feedback')
  } finally {
    feedbackUpdating.value = false
  }
}

function handlePageChange(page: number) {
  pagination.page = page
  loadQueries()
}

function exportCSV() {
  const params: any = {}
  if (searchQuery.value) params.search = searchQuery.value

  api.get('/analytics/export', { params, responseType: 'blob' })
    .then(response => {
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `query_logs_${new Date().toISOString().split('T')[0]}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    })
    .catch(() => {
      message.error('Export failed')
    })
}

onMounted(() => {
  loadStats()
  loadDistribution()
  loadTopDocuments()
  loadQueries()
  loadIntentSpaces()
})
</script>

<style scoped>
.metric-card {
  text-align: center;
}
.metric-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--primary-color);
}
.metric-label {
  font-size: 14px;
  color: #666;
  margin-top: 8px;
}
.chart-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.distribution-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.dist-label {
  width: 80px;
  font-size: 13px;
}
.bar-wrapper {
  flex: 1;
  height: 24px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}
.bar {
  height: 100%;
  background: linear-gradient(90deg, #18a058, #2080f0);
  transition: width 0.3s;
}
.dist-count {
  width: 40px;
  text-align: right;
  font-weight: 600;
}

@media (max-width: 600px) {
  .metric-value {
    font-size: 28px;
  }
}
</style>
