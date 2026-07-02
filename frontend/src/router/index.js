import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/environments',
    children: [
      {
        path: 'environments',
        name: 'environments',
        component: () => import('../views/EnvironmentsView.vue'),
      },
      {
        path: 'environments/:path(.*)',
        name: 'environment-detail',
        component: () => import('../views/EnvironmentDetailView.vue'),
      },
      {
        path: 'instances',
        name: 'instances',
        component: () => import('../views/InstancesView.vue'),
      },
      {
        path: 'users',
        name: 'users',
        component: () => import('../views/UsersView.vue'),
        meta: { admin: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const token = localStorage.getItem('token')
  if (!to.meta.public && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && token) {
    return { name: 'environments' }
  }
  return true
})

export default router
