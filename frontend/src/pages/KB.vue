<template>
  <div>
    <!-- Upload Area -->
    <n-card
      style="margin-bottom: 24px;"
      class="upload-area"
      :class="{ 'drag-over': isDragOver }"
      @click="triggerUpload"
      @dragenter.prevent="onDragEnter"
      @dragover.prevent="onDragOver"
      @dragleave.prevent="onDragLeave"
      @drop.prevent="onDrop"
    >
      <div class="upload-content">
        <n-icon size="48" :color="isDragOver ? '#18a058' : '#999'"><cloud-upload-icon /></n-icon>
        <p>{{ isDragOver ? 'Drop file here' : 'Drag & drop a file here or click to browse' }}</p>
        <p class="hint">Supported formats: PDF, DOCX (max 20MB)</p>
      </div>
      <input
        ref="fileInput"
        type="file"
        accept=".pdf,.docx"
        style="display: none"
        @change="handleFileSelect"
      />
    </n-card>

    <!-- Upload Modal -->
    <n-modal v-model:show="showUploadModal" preset="card" title="Upload Document" :style="isMobile ? 'width: 92vw;' : 'width: 400px;'">
      <p><strong>{{ selectedFile?.name }}</strong></p>
      <n-form style="margin-top: 16px;">
        <n-form-item label="Intent Space (optional)">
          <n-select
            v-model:value="uploadIntentId"
            :options="intentOptions"
            placeholder="Select intent space"
            clearable
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showUploadModal = false">Cancel</n-button>
          <n-button type="primary" @click="uploadDocument" :loading="uploading">Upload</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Edit Intent Modal -->
    <n-modal v-model:show="showEditIntentModal" preset="card" title="Edit Intent Space" :style="isMobile ? 'width: 92vw;' : 'width: 400px;'">
      <p><strong>{{ selectedDocForEdit?.name }}</strong></p>
      <n-form style="margin-top: 16px;">
        <n-form-item label="Intent Space">
          <n-select
            v-model:value="editIntentId"
            :options="intentOptions"
            placeholder="Select intent space"
            clearable
          />
        </n-form-item>
      </n-form>
      <template #footer>
        <n-space justify="end">
          <n-button @click="showEditIntentModal = false">Cancel</n-button>
          <n-button type="primary" @click="saveIntent" :loading="savingIntent">Save</n-button>
        </n-space>
      </template>
    </n-modal>

    <!-- Document Table -->
    <n-card>
      <template #header>
        <n-space vertical justify="space-between" align="stretch">
          <span>Documents</span>
          <n-space :vertical="isMobile" style="gap: 8px;">
            <n-input v-model:value="searchQuery" placeholder="Search..." clearable :style="isMobile ? 'width: 100%;' : 'width: 200px;'" />
            <n-select v-model:value="statusFilter" :options="statusOptions" placeholder="Status" clearable :style="isMobile ? 'width: 100%;' : 'width: 120px;'" />
          </n-space>
        </n-space>
      </template>

      <n-data-table
        :columns="columns"
        :data="documents"
        :pagination="pagination"
        :loading="loading"
        :row-key="(row: any) => row.id"
        :scroll-x="700"
      />

      <n-alert v-if="hasPending" type="info" style="margin-top: 16px;">
        Polling for updates... (checking every 5 seconds while documents are pending)
      </n-alert>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  NCard, NIcon, NButton, NDataTable, NSpace, NInput, NSelect, NModal,
  NForm, NFormItem, NAlert, NTag, NPopconfirm, useMessage, DataTableColumns
} from 'naive-ui'
import { CloudUploadOutline as CloudUploadIcon } from '@vicons/ionicons5'
import api from '@/api'
import type { DocumentResponse, IntentSpaceResponse } from '@/types'

const message = useMessage()
const isMobile = ref(window.innerWidth < 600)
const isTablet = ref(window.innerWidth >= 600 && window.innerWidth < 960)
window.addEventListener('resize', () => {
  isMobile.value = window.innerWidth < 600
  isTablet.value = window.innerWidth >= 600 && window.innerWidth < 960
})

const documents = ref<DocumentResponse[]>([])
const intentSpaces = ref<IntentSpaceResponse[]>([])
const loading = ref(false)
const uploading = ref(false)
const savingIntent = ref(false)
const showUploadModal = ref(false)
const showEditIntentModal = ref(false)
const selectedFile = ref<File | null>(null)
const uploadIntentId = ref<number | null>(null)
const selectedDocForEdit = ref<DocumentResponse | null>(null)
const editIntentId = ref<number | null>(null)
const searchQuery = ref('')
const statusFilter = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const isDragOver = ref(false)

let pollInterval: ReturnType<typeof setInterval> | null = null

const pagination = ref({ page: 1, pageSize: 20, total: 0 })
const page = computed(() => pagination.value.page)
const pageSize = computed(() => pagination.value.pageSize)

const statusOptions = [
  { label: 'Pending', value: 'pending' },
  { label: 'Processed', value: 'processed' },
  { label: 'Error', value: 'error' }
]

const intentOptions = computed(() =>
  intentSpaces.value.map(i => ({ label: i.name, value: i.id }))
)

const hasPending = computed(() => documents.value.some(d => d.status === 'pending'))

// Reset to page 1 when filters change
watch([searchQuery, statusFilter], () => {
  pagination.value.page = 1
  loadDocuments()
})

const columns: DataTableColumns<DocumentResponse> = [
  { title: 'Name', key: 'name', width: 150, ellipsis: true },
  { title: 'Format', key: 'format', width: 80 },
  { title: 'Size', key: 'size_bytes', width: 100, render: (row) => formatSize(row.size_bytes) },
  { title: 'Intent', key: 'intent_space_name', width: 120 },
  {
    title: 'Status',
    key: 'status',
    width: 100,
    render: (row) => {
      const type: any = row.status === 'processed' ? 'success' : row.status === 'error' ? 'error' : 'default'
      return h(NTag, { type, size: 'small' }, { default: () => row.status })
    }
  },
  {
    title: 'Actions',
    key: 'actions',
    width: 180,
    render: (row) => h('div', { class: 'actions-cell' }, [
      h('div', { class: 'actions-line' }, [
        h(NPopconfirm, {
          onPositiveClick: () => reparseDocument(row),
          positiveButtonProps: { type: 'warning' }
        }, {
          trigger: () => h(NButton, { size: 'small', text: true }, { default: () => 'Reparse' }),
          default: () => 'Reparse this document?'
        }),
        h(NButton, { size: 'small', text: true, style: 'margin-left: 16px', onClick: () => updateIntent(row) }, { default: () => 'Edit Intent' })
      ]),
      h('div', { class: 'actions-line' }, [
        h(NPopconfirm, {
          onPositiveClick: () => deleteDocument(row),
          positiveButtonProps: { type: 'error' }
        }, {
          trigger: () => h(NButton, { size: 'small', text: true, type: 'error' }, { default: () => 'Delete' }),
          default: () => 'Delete this document?'
        })
      ])
    ])
  }
]

import { h } from 'vue'

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function loadDocuments() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (searchQuery.value) params.search = searchQuery.value
    if (statusFilter.value) params.status = statusFilter.value

    const response = await api.get('/kb/documents', { params })
    documents.value = response.data.items
    pagination.value.total = response.data.total
  } catch (e) {
    console.error('Failed to load documents:', e)
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

function triggerUpload() {
  fileInput.value?.click()
}

function handleFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (input.files?.length) {
    selectedFile.value = input.files[0]
    showUploadModal.value = true
  }
}

function onDragEnter() {
  isDragOver.value = true
}

function onDragOver() {
  isDragOver.value = true
}

function onDragLeave(e: DragEvent) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  if (
    e.clientX < rect.left ||
    e.clientX >= rect.right ||
    e.clientY < rect.top ||
    e.clientY >= rect.bottom
  ) {
    isDragOver.value = false
  }
}

function onDrop(e: DragEvent) {
  isDragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) {
    selectedFile.value = files[0]
    showUploadModal.value = true
  }
}

async function uploadDocument() {
  if (!selectedFile.value) return

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    await api.post('/kb/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      params: uploadIntentId.value ? { intent_space_id: uploadIntentId.value } : {}
    })

    message.success('Document uploaded successfully')
    showUploadModal.value = false
    selectedFile.value = null
    uploadIntentId.value = null
    await loadDocuments()
    startPolling()
  } catch (e: any) {
    message.error(e.response?.data?.detail || 'Upload failed')
  } finally {
    uploading.value = false
  }
}

async function deleteDocument(doc: DocumentResponse) {
  try {
    await api.delete(`/kb/documents/${doc.id}`)
    message.success('Document deleted')
    await loadDocuments()
  } catch (e) {
    message.error('Delete failed')
  }
}

async function reparseDocument(doc: DocumentResponse) {
  try {
    await api.post(`/kb/documents/${doc.id}/reparse`)
    message.success('Reparse started')
    await loadDocuments()
    startPolling()
  } catch (e) {
    message.error('Reparse failed')
  }
}

function updateIntent(doc: DocumentResponse) {
  selectedDocForEdit.value = doc
  editIntentId.value = doc.intent_space_id
  showEditIntentModal.value = true
}

async function saveIntent() {
  if (!selectedDocForEdit.value) return

  savingIntent.value = true
  try {
    const params = editIntentId.value !== null
      ? { intent_space_id: editIntentId.value }
      : {}
    await api.put(`/kb/documents/${selectedDocForEdit.value.id}/intent`, null, { params })
    message.success('Intent updated')
    showEditIntentModal.value = false
    await loadDocuments()
  } catch (e) {
    message.error('Update failed')
  } finally {
    savingIntent.value = false
  }
}

function startPolling() {
  if (pollInterval) return
  pollInterval = setInterval(() => {
    if (hasPending.value) {
      loadDocuments()
    } else {
      stopPolling()
    }
  }, 5000)
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

onMounted(() => {
  loadDocuments()
  loadIntentSpaces()
})

onUnmounted(stopPolling)
</script>

<style scoped>
.upload-area {
  border: 2px dashed #ddd;
  background: #fafafa;
}
.upload-area:hover {
  border-color: var(--primary-color);
  background: #f0f7ff;
}
.upload-area.drag-over {
  border-color: #18a058;
  background: #f0f7ff;
}
.upload-content {
  text-align: center;
  padding: 24px;
  color: #666;
}
.upload-content .hint {
  font-size: 12px;
  color: #999;
}
.actions-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.actions-line {
  display: flex;
  align-items: center;
}
</style>
