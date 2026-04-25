<template>
  <n-config-provider :theme="lightTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
    <!-- Mobile overlay -->
    <div v-if="isMobile && mobileSidebarVisible" class="sidebar-overlay" @click="mobileSidebarVisible = false" />

    <n-layout has-sider position="absolute" style="height: 100vh">
      <!-- Sidebar -->
      <n-layout-sider
        v-show="!isMobile || mobileSidebarVisible"
        bordered
        collapse-mode="width"
        :collapsed-width="64"
        :width="isMobile ? 240 : 200"
        :collapsed="isMobile ? false : collapsed"
        :inverted="false"
        :class="{ 'mobile-sidebar': isMobile }"
        :native-scrollbar="false"
        show-trigger="bar"
        @collapse="isMobile ? (mobileSidebarVisible = false) : (collapsed = true)"
        @expand="isMobile ? (mobileSidebarVisible = true) : (collapsed = false)"
      >
        <div style="padding: 16px; text-align: center;">
          <h2 v-if="!collapsed" style="color: var(--primary-color);">KMS</h2>
          <n-icon v-else size="24"><LibraryIcon /></n-icon>
        </div>
        <n-menu
          v-model:value="activeKey"
          :collapsed="isMobile ? false : collapsed"
          :collapsed-width="64"
          :collapsed-icon-size="22"
          :options="menuOptions"
          @update:value="handleMenuChange"
        />
      </n-layout-sider>

      <!-- Main Content -->
      <n-layout>
        <n-layout-header bordered style="padding: 16px 24px;">
          <n-space justify="space-between" align="center">
            <n-icon v-if="isMobile" size="20" @click="mobileSidebarVisible = !mobileSidebarVisible" style="cursor: pointer; display: flex; align-items: center;">
              <MenuIcon />
            </n-icon>
            <h3 style="margin: 0;">{{ pageTitle }}</h3>
            <n-icon v-if="isLoggedIn" size="20" @click="handleLogout" style="cursor: pointer; display: flex; align-items: center;">
              <LogOutIcon />
            </n-icon>
          </n-space>
        </n-layout-header>

        <n-layout-content style="padding: 24px">
          <router-view />
        </n-layout-content>
      </n-layout>
    </n-layout>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { ref, computed, watch, h } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { NIcon } from 'naive-ui'
import {
  NLayout, NLayoutSider, NLayoutHeader, NLayoutContent,
  NMenu, NSpace, NConfigProvider, NMessageProvider, lightTheme
} from 'naive-ui'
import {
  Grid as DashboardIcon,
  Link as IntegrationsIcon,
  DocumentText as DocumentIcon,
  Flash as IntentIcon,
  BarChart as AnalyticsIcon,
  Library as LibraryIcon,
  Menu as MenuIcon,
  LogOutOutline as LogOutIcon
} from '@vicons/ionicons5'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const collapsed = ref(false)
const activeKey = ref(route.name as string)
const isMobile = ref(window.innerWidth < 600)
const mobileSidebarVisible = ref(false)

window.addEventListener('resize', () => {
  const wasMobile = isMobile.value
  isMobile.value = window.innerWidth < 600
  if (!wasMobile && isMobile.value) {
    mobileSidebarVisible.value = false
  }
})

// Keep active menu in sync with route on refresh
watch(() => route.name, (name) => {
  activeKey.value = name as string
})

const themeOverrides = {
  Card: {
    color: '#ffffff',
  },
  Layout: {
    color: '#f5f5f5',
  }
}

const isLoggedIn = computed(() => !!authStore.token)

const renderIcon = (icon: typeof DashboardIcon) => () => h(NIcon, null, { default: () => h(icon) })

const menuOptions = [
  {
    label: 'Dashboard',
    key: 'dashboard',
    icon: renderIcon(DashboardIcon)
  },
  {
    label: 'Integrations',
    key: 'integrations',
    icon: renderIcon(IntegrationsIcon)
  },
  {
    label: 'Knowledge Base',
    key: 'kb',
    icon: renderIcon(DocumentIcon)
  },
  {
    label: 'Intent Spaces',
    key: 'intents',
    icon: renderIcon(IntentIcon)
  },
  {
    label: 'Analytics',
    key: 'analytics',
    icon: renderIcon(AnalyticsIcon)
  }
]

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    dashboard: 'Dashboard',
    integrations: 'Integrations',
    kb: 'Knowledge Base',
    intents: 'Intent Spaces',
    analytics: 'Analytics'
  }
  return titles[activeKey.value] || 'KMS'
})

function handleMenuChange(key: string) {
  activeKey.value = key
  router.push({ name: key })
  if (isMobile.value) mobileSidebarVisible.value = false
}

function handleLogout() {
  localStorage.removeItem('kms_token')
  router.push({ name: 'login' })
}
</script>

<style scoped>
.sidebar-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 999;
}
.mobile-sidebar {
  height: 100vh;
  z-index: 1000;
  position: fixed;
}
</style>
