<template>
  <div>
    <n-space style="margin-bottom: 24px;">
      <n-button @click="refresh">
        <template #icon>
          <n-icon><refresh-icon /></n-icon>
        </template>
        Refresh
      </n-button>
    </n-space>

    <n-grid :cols="4" :x-gap="16" :y-gap="16" v-if="loading">
      <n-gi v-for="i in 4" :key="i">
        <n-skeleton height="120px" />
      </n-gi>
    </n-grid>

    <n-grid :cols="4" :x-gap="16" :y-gap="16" v-else>
      <!-- Frontend Integration Card -->
      <n-gi>
        <n-card class="dashboard-card integration" @click="$router.push({ name: 'integrations' })">
          <div class="card-header">
            <n-badge type="info" :dot="integrations.some(i => i.is_active)">
              <n-icon size="24"><plug-icon /></n-icon>
            </n-badge>
            <span class="card-title">Frontend Integration</span>
          </div>
          <div class="card-content">
            <n-tag v-for="int in integrations" :key="int.channel" :type="int.is_active ? 'success' : 'default'">
              {{ int.channel.toUpperCase() }}
            </n-tag>
          </div>
          <div class="card-action">
            <n-button text type="primary">Add Integration →</n-button>
          </div>
        </n-card>
      </n-gi>

      <!-- KB Management Card -->
      <n-gi>
        <n-card class="dashboard-card kb" @click="$router.push({ name: 'kb' })">
          <div class="card-header">
            <n-badge type="success">
              <n-icon size="24"><document-icon /></n-icon>
            </n-badge>
            <span class="card-title">KB Management</span>
          </div>
          <div class="card-stats">
            <div class="stat">
              <span class="stat-value">{{ summary.kb_stats?.total_documents || 0 }}</span>
              <span class="stat-label">Total</span>
            </div>
            <div class="stat">
              <span class="stat-value success">{{ summary.kb_stats?.processed || 0 }}</span>
              <span class="stat-label">Processed</span>
            </div>
            <div class="stat">
              <span class="stat-value warning">{{ summary.kb_stats?.pending || 0 }}</span>
              <span class="stat-label">Pending</span>
            </div>
          </div>
          <div class="card-action">
            <n-button text type="primary">Upload Document →</n-button>
          </div>
        </n-card>
      </n-gi>

      <!-- Intent Configuration Card -->
      <n-gi>
        <n-card class="dashboard-card intent" @click="$router.push({ name: 'intents' })">
          <div class="card-header">
            <n-badge type="warning">
              <n-icon size="24"><flash-icon /></n-icon>
            </n-badge>
            <span class="card-title">Intent Configuration</span>
          </div>
          <div class="card-content">
            <n-tag v-for="space in summary.intent_spaces?.slice(0, 4)" :key="space.id">
              {{ space.name }}
            </n-tag>
          </div>
          <div class="card-action">
            <n-button text type="primary">Create Intent Space →</n-button>
          </div>
        </n-card>
      </n-gi>

      <!-- Analytics Card -->
      <n-gi>
        <n-card class="dashboard-card analytics" @click="$router.push({ name: 'analytics' })">
          <div class="card-header">
            <n-badge type="error">
              <n-icon size="24"><chart-icon /></n-icon>
            </n-badge>
            <span class="card-title">Analytics</span>
          </div>
          <div class="card-big-number">
            {{ summary.analytics?.total_queries || 0 }}
            <span class="big-label">Total Queries</span>
          </div>
          <div class="card-action">
            <n-button text type="primary">View Detailed Logs →</n-button>
          </div>
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { NGrid, NGi, NCard, NIcon, NButton, NSpace, NBadge, NTag, NSkeleton } from 'naive-ui'
import {
  Refresh as RefreshIcon,
  Link as PlugIcon,
  DocumentText as DocumentIcon,
  Flash as FlashIcon,
  BarChart as ChartIcon
} from '@vicons/ionicons5'
import api from '@/api'
import type { DashboardSummary, IntegrationResponse } from '@/types'

const loading = ref(true)
const summary = ref<DashboardSummary>({
  frontend_integrations: [],
  kb_stats: { total_documents: 0, processed: 0, pending: 0, error: 0 },
  intent_spaces: [],
  analytics: { total_queries: 0 }
})
const integrations = ref<IntegrationResponse[]>([])

async function refresh() {
  loading.value = true
  try {
    const response = await api.get('/analytics/dashboard-summary')
    summary.value = response.data
    integrations.value = response.data.frontend_integrations
  } catch (e) {
    console.error('Failed to fetch dashboard:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refresh()
})
</script>

<style scoped>
.dashboard-card {
  cursor: pointer;
  transition: transform 0.2s;
  height: 100%;
}
.dashboard-card:hover {
  transform: translateY(-2px);
}
.dashboard-card.integration { border-top: 3px solid #2080f0; }
.dashboard-card.kb { border-top: 3px solid #18a058; }
.dashboard-card.intent { border-top: 3px solid #722ed1; }
.dashboard-card.analytics { border-top: 3px solid #d46b08; }
.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.card-title {
  font-weight: 600;
  font-size: 14px;
}
.card-content {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.card-stats {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
}
.stat {
  display: flex;
  flex-direction: column;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
}
.stat-value.success { color: #18a058; }
.stat-value.warning { color: #f0a020; }
.stat-label {
  font-size: 12px;
  color: #999;
}
.card-big-number {
  font-size: 48px;
  font-weight: 700;
  line-height: 1.2;
  margin-bottom: 16px;
}
.big-label {
  display: block;
  font-size: 14px;
  font-weight: 400;
  color: #999;
}
.card-action {
  margin-top: auto;
}
</style>
