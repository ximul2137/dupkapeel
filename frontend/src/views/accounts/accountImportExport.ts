import type { AccountConfigItem } from '@/types/accounts'
import { normalizeConfigAccounts, readLegacyStringField } from './accountConfig'

const IMPORT_EXPIRES_AT = '1970-01-01 00:00:00'

type AccountExportFormat = 'json' | 'txt'

const createImportedAccount = (
  email: string,
  mailProvider: AccountConfigItem['mail_provider'],
  overrides: Partial<AccountConfigItem> = {},
): AccountConfigItem => ({
  id: email,
  secure_c_ses: '',
  csesidx: '',
  config_id: '',
  expires_at: IMPORT_EXPIRES_AT,
  mail_provider: mailProvider,
  mail_address: email,
  mail_password: '',
  ...overrides,
})

export const looksLikeJsonImport = (fileName: string, raw: string) =>
  fileName.toLowerCase().endsWith('.json') || raw.startsWith('[') || raw.startsWith('{')

export const parseImportLines = (raw: string) => {
  const items: AccountConfigItem[] = []
  const errors: string[] = []
  const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)

  lines.forEach((line, index) => {
    const parts = line.split('----').map((part) => part.trim())
    const lineNo = index + 1

    if (!parts.length) return

    if (parts[0].toLowerCase() === 'duckmail') {
      if (parts.length < 3 || !parts[1] || !parts[2]) {
        errors.push(`Błędny format w linii ${lineNo} (duckmail)`)
        return
      }
      const email = parts[1]
      const password = parts.slice(2).join('----')
      items.push(createImportedAccount(email, 'duckmail', {
        mail_password: password,
      }))
      return
    }

    if (parts[0].toLowerCase() === 'moemail') {
      if (parts.length < 3 || !parts[1] || !parts[2]) {
        errors.push(`Błędny format w linii ${lineNo} (moemail)`)
        return
      }
      const email = parts[1]
      items.push(createImportedAccount(email, 'moemail', {
        mail_password: parts[2],
      }))
      return
    }

    if (parts[0].toLowerCase() === 'freemail') {
      if (parts.length < 2 || !parts[1]) {
        errors.push(`Błędny format w linii ${lineNo} (freemail)`)
        return
      }
      const email = parts[1]
      if (parts.length >= 6) {
        items.push(createImportedAccount(email, 'freemail', {
          mail_base_url: parts[2] || undefined,
          mail_jwt_token: parts[3] || undefined,
          mail_verify_ssl: parts[4] === 'true' || parts[4] === '1',
          mail_domain: parts[5] || undefined,
        }))
        return
      }
      items.push(createImportedAccount(email, 'freemail'))
      return
    }

    if (parts[0].toLowerCase() === 'gptmail') {
      if (parts.length < 2 || !parts[1]) {
        errors.push(`Błędny format w linii ${lineNo} (gptmail)`)
        return
      }
      items.push(createImportedAccount(parts[1], 'gptmail'))
      return
    }

    if (parts[0].toLowerCase() === 'cfmail') {
      if (parts.length < 2 || !parts[1]) {
        errors.push(`Błędny format w linii ${lineNo} (cfmail)`)
        return
      }
      const email = parts[1]
      items.push(createImportedAccount(email, 'cfmail', {
        mail_password: parts[2] || '',
      }))
      return
    }

    if (parts.length >= 4 && parts[0] && parts[2] && parts[3]) {
      const email = parts[0]
      const password = parts[1] || ''
      const clientId = parts[2]
      const refreshToken = parts.slice(3).join('----')
      items.push(createImportedAccount(email, 'microsoft', {
        mail_password: password,
        mail_client_id: clientId,
        mail_refresh_token: refreshToken,
        mail_tenant: 'consumers',
      }))
      return
    }

    errors.push(`Błędny format w linii ${lineNo}`)
  })

  return { items, errors }
}

export const normalizeJsonImportList = (raw: string) => {
  const parsed = JSON.parse(raw)
  const list = Array.isArray(parsed) ? parsed : parsed?.accounts
  if (!Array.isArray(list)) {
    throw new Error('Błąd formatu JSON: wymagana tablica lub obiekt z polem accounts')
  }

  return normalizeConfigAccounts(
    list.map((item, index) => {
      if (!item || typeof item !== 'object') {
        throw new Error(`Rekord JSON nr ${index + 1} nie jest obiektem`)
      }
      const record = item as Record<string, unknown>
      const legacyMailAddress = typeof record.mail_address === 'string' ? record.mail_address.trim() : ''
      const id = String(record.id || legacyMailAddress || '').trim()
      if (!id) {
        throw new Error(`Rekord JSON nr ${index + 1} nie zawiera id`)
      }

      return {
        ...(record as AccountConfigItem),
        id,
        secure_c_ses: typeof record.secure_c_ses === 'string' ? record.secure_c_ses : '',
        csesidx: typeof record.csesidx === 'string' ? record.csesidx : '',
        config_id: typeof record.config_id === 'string' ? record.config_id : '',
      } as AccountConfigItem
    }),
  )
}

export const mergeJsonImportItems = (existing: AccountConfigItem[], items: AccountConfigItem[]) => {
  const next = [...existing]
  const indexMap = new Map(next.map((account, index) => [account.id, index]))
  const importedIds: string[] = []

  items.forEach((item) => {
    const index = indexMap.get(item.id)
    if (index === undefined) {
      next.push(item)
    } else {
      next[index] = { ...next[index], ...item }
    }
    importedIds.push(item.id)
  })

  return { next, importedIds }
}

export const mergeTextImportItems = (existing: AccountConfigItem[], items: AccountConfigItem[]) => {
  const next = [...existing]
  const indexMap = new Map(next.map((account, index) => [account.id, index]))
  const importedIds: string[] = []

  items.forEach((item) => {
    const index = indexMap.get(item.id)
    if (index === undefined) {
      next.push(item)
      importedIds.push(item.id)
      return
    }

    const current = next[index]
    const updated: AccountConfigItem = {
      ...current,
      mail_provider: item.mail_provider,
      mail_address: item.mail_address,
    }

    if (item.mail_provider === 'microsoft') {
      updated.mail_client_id = item.mail_client_id
      updated.mail_refresh_token = item.mail_refresh_token
      updated.mail_tenant = item.mail_tenant
      updated.mail_password = item.mail_password
    } else {
      updated.mail_password = item.mail_password
      updated.mail_client_id = undefined
      updated.mail_refresh_token = undefined
      updated.mail_tenant = undefined
      updated.mail_base_url = item.mail_base_url
      updated.mail_jwt_token = item.mail_jwt_token
      updated.mail_verify_ssl = item.mail_verify_ssl
      updated.mail_domain = item.mail_domain
    }

    next[index] = updated
    importedIds.push(item.id)
  })

  return { next, importedIds }
}

export const buildAccountExportPayload = (
  list: AccountConfigItem[],
  format: AccountExportFormat,
  timestamp = new Date().toISOString().replace(/[:.]/g, '-'),
) => {
  if (format === 'json') {
    return {
      content: JSON.stringify(list, null, 2),
      filename: `accounts-${timestamp}.json`,
      mime: 'application/json',
      successMessage: 'Wyeksportowano JSON',
    }
  }

  const lines = list.map((item) => {
    const provider = readLegacyStringField(item, 'mail_provider').toLowerCase()
    const email = readLegacyStringField(item, 'mail_address') || item.id || ''
    if (!email) return ''
    if (provider === 'moemail') {
      return `moemail----${email}----${readLegacyStringField(item, 'mail_password')}`
    }
    if (provider === 'freemail') {
      return `freemail----${email}`
    }
    if (provider === 'gptmail') {
      return `gptmail----${email}`
    }
    if (provider === 'cfmail') {
      return `cfmail----${email}----${readLegacyStringField(item, 'mail_password')}`
    }
    if (provider === 'duckmail') {
      return `duckmail----${email}----${readLegacyStringField(item, 'mail_password')}`
    }
    if (
      provider === 'microsoft'
      || readLegacyStringField(item, 'mail_client_id')
      || readLegacyStringField(item, 'mail_refresh_token')
    ) {
      return `${email}----${readLegacyStringField(item, 'mail_password')}----${readLegacyStringField(item, 'mail_client_id')}----${readLegacyStringField(item, 'mail_refresh_token')}`
    }
    if (readLegacyStringField(item, 'mail_password')) {
      return `duckmail----${email}----${readLegacyStringField(item, 'mail_password')}`
    }
    return email
  }).filter(Boolean)

  return {
    content: lines.join('\n'),
    filename: `accounts-${timestamp}.txt`,
    mime: 'text/plain',
    successMessage: 'Wyeksportowano TXT',
  }
}
