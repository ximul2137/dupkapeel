import apiClient from './client'
import type {
  AccountActionResponse,
  AccountBulkActionResponse,
  AccountConfigItem,
  AccountConfigUpdateResponse,
  AccountsConfigResponse,
  AccountsListParams,
  AccountsListResponse,
} from '@/types/accounts'

export const accountsApi = {
  list: (params?: AccountsListParams) =>
    apiClient.get<never, AccountsListResponse>('/admin/accounts', {
      params: {
        page: params?.page,
        page_size: params?.pageSize,
        query: params?.query,
        status: params?.status,
      },
    }),

  getConfig: () =>
    apiClient.get<never, AccountsConfigResponse>('/admin/accounts-config'),

  updateConfig: (accounts: AccountConfigItem[]) =>
    apiClient.put<AccountConfigItem[], AccountConfigUpdateResponse>('/admin/accounts-config', accounts),

  delete: (accountId: string) =>
    apiClient.delete<never, AccountActionResponse>(`/admin/accounts/${accountId}`),

  disable: (accountId: string) =>
    apiClient.put<never, AccountActionResponse>(`/admin/accounts/${accountId}/disable`),

  enable: (accountId: string) =>
    apiClient.put<never, AccountActionResponse>(`/admin/accounts/${accountId}/enable`),

  bulkEnable: (accountIds: string[]) =>
    apiClient.put<string[], AccountBulkActionResponse>('/admin/accounts/bulk-enable', accountIds),

  bulkDisable: (accountIds: string[]) =>
    apiClient.put<string[], AccountBulkActionResponse>('/admin/accounts/bulk-disable', accountIds),

  bulkDelete: (accountIds: string[]) =>
    apiClient.put<string[], AccountBulkActionResponse>('/admin/accounts/bulk-delete', accountIds),
}
