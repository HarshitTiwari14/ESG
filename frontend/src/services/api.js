import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({ baseURL: BASE })

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('access_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

api.interceptors.response.use(
  r => r,
  async err => {
    if (err.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token')
      if (refresh) {
        try {
          const { data } = await axios.post(`${BASE}/auth/token/refresh/`, { refresh })
          localStorage.setItem('access_token', data.access)
          err.config.headers.Authorization = `Bearer ${data.access}`
          return api.request(err.config)
        } catch {
          localStorage.clear()
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(err)
  }
)

export const auth = {
  login: (username, password) =>
    api.post('/auth/token/', { username, password }),
  me: () => api.get('/auth/me/'),
}

export const batches = {
  list: () => api.get('/batches/'),
  lock: id => api.post(`/batches/${id}/lock/`),
}

export const records = {
  list: (params) => api.get('/records/', { params }),
  get: id => api.get(`/records/${id}/`),
  approve: id => api.post(`/records/${id}/approve/`),
  flag: (id, reason) => api.post(`/records/${id}/flag/`, { reason }),
  unflag: id => api.post(`/records/${id}/unflag/`),
}

export const dashboard = {
  stats: () => api.get('/dashboard/stats/'),
}

export const upload = (formData) =>
  api.post('/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })

export default api
