import { accountsApi } from '@/api'
import type { AccountConfigItem } from '@/types/accounts'

export type AccountEditForm = {
  id: string
  secure_c_ses: string
  csesidx: string
  config_id: string
  host_c_oses: string
  expires_at: string
}

const MASK_FIELDS = new Set([
  'secure_c_ses',
  'csesidx',
  'config_id',
  'host_c_oses',
  'mail_password',
  'mail_refresh_token',
  'mail_client_id',
  'mail_api_key',
  'mail_jwt_token',
])

export const createEmptyAccountEditForm = (): AccountEditForm => ({
  id: '',
  secure_c_ses: '',
  csesidx: '',
  config_id: '',
  host_c_oses: '',
  expires_at: '',
})

export const readLegacyStringField = (account: AccountConfigItem, field: string) => {
  const value = account[field]
  return typeof value === 'string' ? value.trim() : ''
}

export const getConfigId = (account: AccountConfigItem, index: number) =>
  account.id || readLegacyStringField(account, 'mail_address') || `account_${index + 1}`

export const normalizeConfigAccounts = (accounts: AccountConfigItem[]) =>
  accounts.map((account, index) => ({
    ...account,
    id: getConfigId(account, index),
  }))

export const loadAccountConfigList = async () => {
  const response = await accountsApi.getConfig()
  return normalizeConfigAccounts(Array.isArray(response.accounts) ? response.accounts : [])
}

export const createAccountEditForm = (account: AccountConfigItem): AccountEditForm => ({
  id: account.id,
  secure_c_ses: account.secure_c_ses,
  csesidx: account.csesidx,
  config_id: account.config_id,
  host_c_oses: account.host_c_oses || '',
  expires_at: account.expires_at || '',
})

export const applyAccountEditForm = (
  accounts: AccountConfigItem[],
  index: number,
  form: AccountEditForm,
) => {
  if (index < 0 || index >= accounts.length) {
    return [...accounts]
  }

  const next = [...accounts]
  next[index] = {
    ...next[index],
    id: form.id.trim(),
    secure_c_ses: form.secure_c_ses.trim(),
    csesidx: form.csesidx.trim(),
    config_id: form.config_id.trim(),
    host_c_oses: form.host_c_oses.trim() || undefined,
    expires_at: form.expires_at.trim() || undefined,
  }
  return next
}

export const parseConfigEditorJson = (raw: string) => {
  const parsed = JSON.parse(raw)
  if (!Array.isArray(parsed)) {
    throw new Error('Format konfiguracji musi być tablicą.')
  }
  return normalizeConfigAccounts(parsed as AccountConfigItem[])
}

const maskValue = (value: unknown) => {
  if (typeof value !== 'string') return value
  if (!value) return value
  if (value.length <= 6) return `${value.slice(0, 2)}****`
  return `${value.slice(0, 3)}****`
}

export const maskConfig = (list: AccountConfigItem[]) =>
  list.map((item) => {
    const next = { ...item } as Record<string, unknown>
    MASK_FIELDS.forEach((field) => {
      if (next[field]) {
        next[field] = maskValue(next[field])
      }
    })
    return next as AccountConfigItem
  })
