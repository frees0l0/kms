import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/pages/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('@/pages/Dashboard.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/integrations',
    name: 'integrations',
    component: () => import('@/pages/Integrations.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/kb',
    name: 'kb',
    component: () => import('@/pages/KB.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/intents',
    name: 'intents',
    component: () => import('@/pages/Intents.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/analytics',
    name: 'analytics',
    component: () => import('@/pages/Analytics.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/',
    redirect: '/dashboard'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('kms_token')
  const requiresAuth = to.matched.some(r => r.meta.requiresAuth !== false)

  if (requiresAuth && !token) {
    next({ name: 'login' })
  } else if (to.name === 'login' && token) {
    next({ name: 'dashboard' })
  } else {
    next()
  }
})

export default router
