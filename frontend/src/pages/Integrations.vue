<template>
  <div>
    <n-grid :cols="gridCols" :x-gap="24" :y-gap="24">
      <!-- Telegram Card -->
      <n-gi v-if="telegramIntegration">
        <n-card
          class="integration-card"
          :class="{ active: telegramActive }"
        >
          <div class="integration-header">
            <n-icon size="32" color="#0088cc"><telegram-icon /></n-icon>
            <div>
              <h3>Telegram</h3>
              <n-tag :type="telegramActive ? 'success' : 'default'" size="small">
                {{ telegramActive ? 'Connected' : 'Disconnected' }}
              </n-tag>
            </div>
          </div>
          <div class="integration-info">
            <p v-if="telegramIntegration?.config_hint">{{ telegramIntegration.config_hint }}</p>
            <p v-else class="hint">Not configured</p>
          </div>
          <div class="integration-actions">
            <n-button type="primary" size="small" @click.stop="testChannel('telegram')" :loading="testing === 'telegram'">
              Test
            </n-button>
          </div>
        </n-card>
      </n-gi>

      <!-- Discord Card -->
      <n-gi v-if="discordIntegration">
        <n-card
          class="integration-card"
          :class="{ active: discordActive }"
        >
          <div class="integration-header">
            <n-icon size="32" color="#5865f2"><discord-icon /></n-icon>
            <div>
              <h3>Discord</h3>
              <n-tag :type="discordActive ? 'success' : 'default'" size="small">
                {{ discordActive ? 'Connected' : 'Disconnected' }}
              </n-tag>
            </div>
          </div>
          <div class="integration-info">
            <p v-if="discordIntegration?.config_hint">{{ discordIntegration.config_hint }}</p>
            <p v-else class="hint">Not configured</p>
          </div>
          <div class="integration-actions">
            <n-button type="primary" size="small" @click.stop="testChannel('discord')" :loading="testing === 'discord'">
              Test
            </n-button>
          </div>
        </n-card>
      </n-gi>

      <!-- Teams Card -->
      <n-gi v-if="teamsIntegration">
        <n-card
          class="integration-card"
          :class="{ active: teamsActive }"
        >
          <div class="integration-header">
            <n-icon size="32" color="#5059c9"><teams-icon /></n-icon>
            <div>
              <h3>Microsoft Teams</h3>
              <n-tag :type="teamsActive ? 'success' : 'default'" size="small">
                {{ teamsActive ? 'Connected' : 'Disconnected' }}
              </n-tag>
            </div>
          </div>
          <div class="integration-info">
            <p v-if="teamsIntegration?.config_hint">{{ teamsIntegration.config_hint }}</p>
            <p v-else class="hint">Not configured</p>
          </div>
          <div class="integration-actions">
            <n-button type="primary" size="small" @click.stop="testChannel('teams')" :loading="testing === 'teams'">
              Test
            </n-button>
          </div>
        </n-card>
      </n-gi>
    </n-grid>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  NGrid, NGi, NCard, NIcon, NButton, NTag, useMessage
} from 'naive-ui'
import { Send as TelegramIcon, LogoWindows as TeamsIcon, LogoDiscord as DiscordIcon } from '@vicons/ionicons5'
import api from '@/api'

const message = useMessage()
const isMobile = ref(window.innerWidth < 600)
const isTablet = ref(window.innerWidth >= 600 && window.innerWidth < 960)

const gridCols = computed(() => {
  if (isMobile.value) return 1
  if (isTablet.value) return 2
  return 3
})

window.addEventListener('resize', () => {
  isMobile.value = window.innerWidth < 600
  isTablet.value = window.innerWidth >= 600 && window.innerWidth < 960
})

const integrations = ref<any[]>([])
const testing = ref('')

const telegramIntegration = computed(() => integrations.value.find(i => i.channel === 'telegram'))
const teamsIntegration = computed(() => integrations.value.find(i => i.channel === 'teams'))
const discordIntegration = computed(() => integrations.value.find(i => i.channel === 'discord'))
const telegramActive = computed(() => telegramIntegration.value?.is_active || false)
const teamsActive = computed(() => teamsIntegration.value?.is_active || false)
const discordActive = computed(() => discordIntegration.value?.is_active || false)

async function loadIntegrations() {
  try {
    const response = await api.get('/integrations')
    integrations.value = response.data.data
  } catch (e) {
    console.error('Failed to load integrations:', e)
  }
}

async function testChannel(channel: string) {
  testing.value = channel
  try {
    const response = await api.post(`/integrations/${channel}/test`)
    if (response.data.status === 'success') {
      message.success('Test message sent successfully')
    } else {
      message.warning(response.data.message || 'Test failed')
    }
    await loadIntegrations()
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Test failed')
  } finally {
    testing.value = ''
  }
}

onMounted(loadIntegrations)
</script>

<style scoped>
.integration-card {
  transition: all 0.2s;
}
.integration-card.active {
  border-color: #18a058;
}
.integration-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}
.integration-header h3 {
  margin: 0 0 8px 0;
}
.integration-info {
  margin-bottom: 16px;
  color: #666;
}
.integration-info .hint {
  color: #999;
  font-style: italic;
}
.integration-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
