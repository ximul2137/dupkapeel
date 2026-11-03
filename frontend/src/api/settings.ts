import apiClient from './client'
import type { Settings } from '@/types/settings'

export const settingsApi = {
  get: () =>
    apiClient.get<never, Settings>('/admin/settings'),

  update: (settings: Settings) =>
    apiClient.put<Settings, Settings>('/admin/settings', settings),
}
