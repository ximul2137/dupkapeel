import axios, { type AxiosInstance, type AxiosError } from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

export const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30000,
  withCredentials: true,
})

apiClient.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
)

let isRedirecting = false

apiClient.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError) => {
    const rawHeaders = (error.config?.headers || {}) as Record<string, unknown>
    const skipAuthRedirectHeader = rawHeaders['X-Skip-Auth-Redirect'] ?? rawHeaders['x-skip-auth-redirect']
    const skipAuthRedirect = String(skipAuthRedirectHeader ?? '') === '1'

    if (error.response?.status === 401 && !isRedirecting && !skipAuthRedirect) {
      isRedirecting = true
      const authStore = useAuthStore()
      authStore.isLoggedIn = false
      await router.push('/login')
      isRedirecting = false
    }

    const errorMessage = resolveErrorMessage(error)

    const wrapped = new Error(errorMessage || 'Żądanie nie powiodło się') as Error & {
      status?: number
      data?: unknown
    }
    wrapped.status = error.response?.status
    wrapped.data = error.response?.data

    return Promise.reject(wrapped)
  }
)

export default apiClient

function resolveErrorMessage(error: AxiosError) {
  const data = error.response?.data as any

  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((item: any) => {
        const location = Array.isArray(item?.loc) ? item.loc.slice(1).join('.') : ''
        const message = String(item?.msg || '').trim()
        return location ? `${location}: ${message}` : message
      })
      .filter(Boolean)
      .join('\n')
  }

  if (typeof data?.detail === 'string' && data.detail.trim()) {
    return data.detail.trim()
  }

  if (typeof data?.message === 'string' && data.message.trim()) {
    return data.message.trim()
  }

  return error.message
}
