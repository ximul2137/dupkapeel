import apiClient from './client'
import type { AdminLogsResponse } from '@/types/api'

export const logsApi = {
  // Pobierz logi
  list: (params?: { limit?: number; level?: string; search?: string }) =>
    apiClient.get<never, AdminLogsResponse>('/admin/log', { params }),

  // Wyczyść logi
  clear: () =>
    apiClient.delete('/admin/log?confirm=yes'),
}
