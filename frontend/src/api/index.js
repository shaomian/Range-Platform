import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    if (status === 401) {
      localStorage.removeItem('token')
      if (router.currentRoute.value.name !== 'login') {
        router.push({ name: 'login' })
      }
    }
    if (detail && status !== 401) {
      ElMessage.error(typeof detail === 'string' ? detail : '请求失败')
    }
    return Promise.reject(error)
  }
)

export const authApi = {
  login(username, password) {
    const form = new URLSearchParams()
    form.append('username', username)
    form.append('password', password)
    return api.post('/auth/login', form)
  },
  me: () => api.get('/auth/me'),
}

export const envApi = {
  list: (params) => api.get('/environments', { params }),
  meta: () => api.get('/environments/meta'),
  detail: (path) => api.get(`/environments/${path}`),
  reload: () => api.post('/environments/reload'),
}

export const instanceApi = {
  list: (all = false) => api.get('/instances', { params: { all } }),
  start: (envPath) => api.post('/instances', { env_path: envPath }),
  stop: (id) => api.post(`/instances/${id}/stop`),
  renew: (id, minutes) => api.post(`/instances/${id}/renew`, { minutes }),
  remove: (id) => api.delete(`/instances/${id}`),
  logs: (id, tail = 500) => api.get(`/instances/${id}/logs`, { params: { tail } }),
  status: (id) => api.get(`/instances/${id}/status`),
}

export const settingsApi = {
  get: () => api.get('/settings'),
  update: (data) => api.put('/settings', data),
}

export const userApi = {
  list: () => api.get('/users'),
  create: (data) => api.post('/users', data),
  update: (id, data) => api.patch(`/users/${id}`, data),
  remove: (id) => api.delete(`/users/${id}`),
}

export default api
