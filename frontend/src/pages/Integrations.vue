<template>
  <div>
    <n-grid :cols="2" :x-gap="24" :y-gap="24">
      <!-- Telegram Card -->
      <n-gi>
        <n-card
          class="integration-card"
          :class="{ active: telegramActive }"
          @click="openModal('telegram')"
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
            <p v-else class="hint">Not configured - click to add</p>
          </div>
          <div class="integration-actions">
            <n-button type="primary" size="small" @click.stop="testChannel('telegram')" :loading="testing === 'telegram'">
              Test
            </n-button>
          </div>
        </n-card>
      </n-gi>

      <!-- Teams Card -->
      <n-gi>
        <n-card
          class="integration-card"
          :class="{ active: teamsActive }"
          @click="openModal('teams')"
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
            <p v-else class="hint">Not configured - click to add</p>
          </div>
          <div class="integration-actions">
            <n-button type="primary" size="small" @click.stop="testChannel('teams')" :loading="testing === 'teams'">
              Test
            </n-button>
          </div>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- Config Modal -->
    <n-modal v-model:show="showModal" preset="card" :title="`Configure ${modalChannel}`" style="width: 500px;">
      <n-form v-if="modalChannel === 'telegram'" :model="telegramForm">
        <n-form-item label="Bot Token" required>
          <n-input v-model:value="telegramForm.token" placeholder="123456:ABCdefGHI..." show-password-on="click" />
        </n-form-item>
      </n-form>
      <n-form v-else :model="teamsForm">
        <n-form-item label="App ID" required>
          <n-input v-model:value="teamsForm.app_id" placeholder="your-app-id" />
        </n-form-item>
        <n-form-item label="App Secret" required>
          <n-input v-model:value="teamsForm.app_secret" type="password" show-password-on="click" />
        </n-form-item>
        <n-form-item label="Tenant ID">
          <n-input v-model:value="teamsForm.tenant_id" placeholder="common" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showModal = false">Cancel</n-button>
          <n-button type="primary" @click="saveConfig" :loading="saving">Save</n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  NGrid, NGi, NCard, NIcon, NButton, NTag, NModal, NForm, NFormItem,
  NInput, NSpace, useMessage
} from 'naive-ui'
import { Send as TelegramIcon, LogoWindows as TeamsIcon } from '@vicons/ionicons5'
import api from '@/api'

const message = useMessage()

const integrations = ref<any[]>([])
const showModal = ref(false)
const modalChannel = ref('')
const saving = ref(false)
const testing = ref('')

const telegramForm = ref({ token: '' })
const teamsForm = ref({ app_id: '', app_secret: '', tenant_id: 'common' })

const telegramIntegration = computed(() => integrations.value.find(i => i.channel === 'telegram'))
const teamsIntegration = computed(() => integrations.value.find(i => i.channel === 'teams'))
const telegramActive = computed(() => telegramIntegration.value?.is_active || false)
const teamsActive = computed(() => teamsIntegration.value?.is_active || false)

async function loadIntegrations() {
  try {
    const response = await api.get('/integrations')
    integrations.value = response.data.data
  } catch (e) {
    console.error('Failed to load integrations:', e)
  }
}

function openModal(channel: string) {
  modalChannel.value = channel
  if (channel === 'telegram') {
    if (telegramIntegration.value?.config_hint) {
      message.info('Please enter a new token to update (previous token cannot be shown)')
    }
    telegramForm.value = { token: '' }
  } else {
    if (teamsIntegration.value?.config_hint) {
      message.info('Please enter new credentials to update (previous cannot be shown)')
    }
    teamsForm.value = { app_id: '', app_secret: '', tenant_id: 'common' }
  }
  showModal.value = true
}

async function saveConfig() {
  saving.value = true
  try {
    if (modalChannel.value === 'telegram') {
      await api.post('/integrations/telegram', { token: telegramForm.value.token })
    } else {
      await api.post('/integrations/teams', teamsForm.value)
    }
    message.success('Configuration saved')
    showModal.value = false
    await loadIntegrations()
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Failed to save')
  } finally {
    saving.value = false
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
  cursor: pointer;
  transition: all 0.2s;
}
.integration-card:hover {
  border-color: var(--primary-color);
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
