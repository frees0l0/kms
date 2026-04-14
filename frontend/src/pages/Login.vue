<template>
  <div style="display: flex; height: 100%; justify-content: center; align-items: center;">
    <n-card style="width: 400px;" title="KMS Login">
      <n-form ref="formRef" :model="form" :rules="rules">
        <n-form-item path="username" label="Username">
          <n-input v-model:value="form.username" placeholder="admin" />
        </n-form-item>
        <n-form-item path="password" label="Password">
          <n-input v-model:value="form.password" type="password" show-password-on="click" />
        </n-form-item>
        <n-button type="primary" block :loading="loading" @click="handleLogin">
          Login
        </n-button>
      </n-form>
      <n-alert v-if="error" type="error" style="margin-top: 16px;">
        {{ error }}
      </n-alert>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { NCard, NForm, NFormItem, NInput, NButton, NAlert, FormInst } from 'naive-ui'
import api from '@/api'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref<FormInst | null>(null)
const loading = ref(false)
const error = ref('')

const form = ref({
  username: '',
  password: ''
})

const rules = {
  username: { required: true, message: 'Username is required', trigger: 'blur' },
  password: { required: true, message: 'Password is required', trigger: 'blur' }
}

async function handleLogin() {
  if (!formRef.value) return

  formRef.value.validate(async (errors) => {
    if (errors) return

    loading.value = true
    error.value = ''

    try {
      const response = await api.post('/auth/login/json', null, {
        params: {
          username: form.value.username,
          password: form.value.password
        }
      })
      authStore.setToken(response.data.access_token)
      router.push({ name: 'dashboard' })
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Login failed'
    } finally {
      loading.value = false
    }
  })
}
</script>
