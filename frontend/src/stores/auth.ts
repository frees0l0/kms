import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('kms_token') || '')

  function setToken(newToken: string) {
    token.value = newToken
    localStorage.setItem('kms_token', newToken)
  }

  function clearToken() {
    token.value = ''
    localStorage.removeItem('kms_token')
  }

  return { token, setToken, clearToken }
})
