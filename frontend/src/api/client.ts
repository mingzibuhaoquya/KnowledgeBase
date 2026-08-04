import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8018/api/v1',
  timeout: 30000
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('kb_access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
