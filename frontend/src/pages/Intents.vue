<template>
  <div>
    <!-- Intent Space Cards -->
    <n-grid :cols="gridCols" :x-gap="16" :y-gap="16" style="margin-bottom: 24px;">
      <n-gi v-for="space in intentSpaces" :key="space.id">
        <n-card class="intent-card">
          <div class="intent-header">
            <h4>{{ space.name }}</h4>
            <n-space>
              <n-button size="tiny" circle @click="editIntent(space)">
                <template #icon><n-icon><edit-icon /></n-icon></template>
              </n-button>
              <n-popconfirm @positive-click="deleteIntent(space)">
                <template #trigger>
                  <n-button size="tiny" circle type="error">
                    <template #icon><n-icon><trash-icon /></n-icon></template>
                  </n-button>
                </template>
                Delete "{{ space.name }}"?
              </n-popconfirm>
            </n-space>
          </div>
          <p class="intent-desc">{{ space.description || 'No description' }}</p>
          <div class="intent-stats">
            <span>{{ space.document_count }} documents</span>
            <span v-if="space.accuracy">Accuracy: {{ (space.accuracy * 100).toFixed(0) }}%</span>
          </div>
          <n-space v-if="space.keywords" style="margin-top: 8px;">
            <n-tag v-for="kw in space.keywords.split(',').map(k => k.trim()).filter(k => k)" :key="kw" size="small">
              {{ kw }}
            </n-tag>
          </n-space>
        </n-card>
      </n-gi>
      <n-gi>
        <n-card class="intent-card add-card" @click="showCreateModal = true">
          <div class="add-card-content">
            <n-icon size="32" color="#999"><add-icon /></n-icon>
            <p>Create Intent Space</p>
          </div>
        </n-card>
      </n-gi>
    </n-grid>

    <!-- Create/Edit Modal -->
    <n-modal v-model:show="showCreateModal" preset="card" :title="editingId ? 'Edit Intent Space' : 'Create Intent Space'" :style="isMobile ? 'width: 92vw;' : 'width: 500px;'">
      <n-form :model="form" label-placement="top">
        <n-form-item label="Name" required>
          <n-input v-model:value="form.name" placeholder="e.g., HR, Legal, Finance" />
        </n-form-item>
        <n-form-item label="Description">
          <n-input v-model:value="form.description" type="textarea" placeholder="Brief description..." />
        </n-form-item>
        <n-form-item label="Keywords">
          <n-input v-model:value="form.keywords" placeholder="vacation, leave, salary (comma-separated)" />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="closeModal">Cancel</n-button>
          <n-button type="primary" @click="saveIntent" :loading="saving">
            {{ editingId ? 'Update' : 'Create' }}
          </n-button>
        </n-space>
      </template>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  NGrid, NGi, NCard, NIcon, NButton, NSpace, NTag, NModal, NForm,
  NFormItem, NInput, NPopconfirm, useMessage
} from 'naive-ui'
import {
  AddOutline as AddIcon,
  CreateOutline as EditIcon,
  TrashOutline as TrashIcon
} from '@vicons/ionicons5'
import api from '@/api'
import type { IntentSpaceResponse } from '@/types'

const message = useMessage()
const isMobile = ref(window.innerWidth < 600)
const isTablet = ref(window.innerWidth >= 600 && window.innerWidth < 960)

const gridCols = computed(() => {
  if (isMobile.value) return 1
  if (isTablet.value) return 2
  return 4
})

window.addEventListener('resize', () => {
  isMobile.value = window.innerWidth < 600
  isTablet.value = window.innerWidth >= 600 && window.innerWidth < 960
})

const intentSpaces = ref<IntentSpaceResponse[]>([])
const showCreateModal = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)

const form = ref({
  name: '',
  description: '',
  keywords: ''
})

async function loadIntentSpaces() {
  try {
    const response = await api.get('/intents')
    intentSpaces.value = response.data.data
  } catch (e) {
    console.error('Failed to load intent spaces:', e)
  }
}

function editIntent(space: IntentSpaceResponse) {
  editingId.value = space.id
  form.value = {
    name: space.name,
    description: space.description || '',
    keywords: space.keywords || ''
  }
  showCreateModal.value = true
}

function closeModal() {
  showCreateModal.value = false
  editingId.value = null
  form.value = { name: '', description: '', keywords: '' }
}

async function saveIntent() {
  if (!form.value.name.trim()) {
    message.error('Name is required')
    return
  }

  saving.value = true
  try {
    if (editingId.value) {
      await api.put(`/intents/${editingId.value}`, form.value)
      message.success('Intent space updated')
    } else {
      await api.post('/intents', form.value)
      message.success('Intent space created')
    }
    closeModal()
    await loadIntentSpaces()
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Operation failed')
  } finally {
    saving.value = false
  }
}

async function deleteIntent(space: IntentSpaceResponse) {
  try {
    await api.delete(`/intents/${space.id}`)
    message.success('Intent space deleted')
    await loadIntentSpaces()
  } catch (e) {
    message.error('Delete failed')
  }
}

onMounted(loadIntentSpaces)
</script>

<style scoped>
.intent-card {
  height: 100%;
}
.intent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.intent-header h4 {
  margin: 0;
}
.intent-desc {
  color: #666;
  font-size: 13px;
  margin-bottom: 8px;
}
.intent-stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #999;
}
.add-card {
  cursor: pointer;
  border: 2px dashed #ddd;
  background: transparent;
}
.add-card:hover {
  border-color: var(--primary-color);
  background: #f0f7ff;
}
.add-card-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 150px;
  color: #999;
}
</style>
