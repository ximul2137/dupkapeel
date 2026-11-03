export interface QuotaStatus {
  available: boolean
  remaining_seconds?: number
  reason?: string
  daily_used?: number
  daily_limit?: number
}

export interface AccountQuotaStatus {
  quotas: {
    text: QuotaStatus
    images: QuotaStatus
    videos: QuotaStatus
  }
  limited_count: number
  total_count: number
  is_expired: boolean
}

export type AccountStateCode =
  | 'active'
  | 'manual_disabled'
  | 'access_restricted'
  | 'expired'
  | 'expiring_soon'
  | 'rate_limited'
  | 'quota_limited'
  | 'unavailable'
  | 'unknown'

export type AccountStateSeverity = 'success' | 'warning' | 'danger' | 'muted'

export interface AccountState {
  code: AccountStateCode
  label: string
  severity: AccountStateSeverity
  reason: string | null
  cooldown_seconds: number
  can_enable: boolean
  can_disable: boolean
  can_delete: boolean
}

export interface AdminAccount {
  id: string
  state?: AccountState
  status: string
  expires_at: string
  remaining_hours: number | null
  remaining_display: string
  is_available: boolean
  failure_count: number
  disabled: boolean
  disabled_reason: string | null
  cooldown_seconds: number
  cooldown_reason: string | null
  conversation_count: number
  session_usage_count: number
  quota_status: AccountQuotaStatus
  trial_end: string | null
  trial_days_remaining: number | null
}

export type AccountListStatus = 'all' | AccountStateCode

export interface AccountsListParams {
  page?: number
  pageSize?: number
  query?: string
  status?: AccountListStatus
}

export interface AccountsListResponse {
  total: number
  page: number
  page_size: number
  total_pages: number
  query: string
  status: AccountListStatus
  accounts: AdminAccount[]
}

export interface AccountConfigItem {
  id: string
  secure_c_ses: string
  csesidx: string
  config_id: string
  host_c_oses?: string
  expires_at?: string
  mail_provider?: string
  mail_address?: string
  mail_password?: string
  mail_client_id?: string
  mail_refresh_token?: string
  mail_tenant?: string
  mail_base_url?: string
  mail_api_key?: string
  mail_jwt_token?: string
  mail_verify_ssl?: boolean
  mail_domain?: string
  disabled?: boolean
  disabled_reason?: string | null
  trial_end?: string | null
  [key: string]: unknown
}

export interface AccountsConfigResponse {
  accounts: AccountConfigItem[]
}

export interface AccountActionResponse {
  status: string
  message: string
  account_count: number
}

export interface AccountConfigUpdateResponse {
  status: string
  message: string
  account_count: number
}

export interface AccountBulkActionResponse {
  status: string
  success_count: number
  errors: string[]
}
