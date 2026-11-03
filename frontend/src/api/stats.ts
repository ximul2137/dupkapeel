import apiClient from './client'
import type { AdminStats, DashboardTimeRange } from '@/types/dashboard'

export const statsApi = {
  overview(timeRange: DashboardTimeRange = '24h') {
    return apiClient.get<never, AdminStats>('/admin/stats', {
      params: { time_range: timeRange },
    })
  },
}
