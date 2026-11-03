import type { RefreshSettings, Settings } from '@/types/settings'
import { createDefaultRefreshSettings } from './settingsDefaults'
import { SETTINGS_LIMITS } from './settingsConstraints'
import {
  normalizeDecimal,
  normalizeBrowserMode,
  normalizeInteger,
  normalizeTempMailProvider,
  pickBoolean,
  pickString,
} from './settingsHelpers'

export const hydrateRefreshSettings = (source: Partial<Settings>): RefreshSettings => {
  const defaults = createDefaultRefreshSettings()
  const current: Partial<RefreshSettings> = source.refresh_settings ?? {}
  const browserMode = normalizeBrowserMode(
    current.browser_mode,
    current.browser_headless,
  )

  return {
    ...defaults,
    ...current,
    proxy_for_auth: pickString(defaults.proxy_for_auth ?? '', current.proxy_for_auth),
    temp_mail_provider: normalizeTempMailProvider(current.temp_mail_provider),
    mail_proxy_enabled: pickBoolean(defaults.mail_proxy_enabled ?? false, current.mail_proxy_enabled),
    browser_mode: browserMode,
    browser_headless: browserMode === 'headless',
    refresh_window_hours: normalizeInteger(
      defaults.refresh_window_hours ?? 1,
      SETTINGS_LIMITS.refresh.refreshWindowHours.min,
      SETTINGS_LIMITS.refresh.refreshWindowHours.max,
      current.refresh_window_hours,
    ),
    register_domain: pickString(defaults.register_domain ?? '', current.register_domain),
    register_default_count: normalizeInteger(
      defaults.register_default_count ?? 20,
      SETTINGS_LIMITS.refresh.registerDefaultCount.min,
      SETTINGS_LIMITS.refresh.registerDefaultCount.max,
      current.register_default_count,
    ),
    auto_refresh_accounts_seconds: normalizeInteger(
      defaults.auto_refresh_accounts_seconds ?? 60,
      SETTINGS_LIMITS.refresh.autoRefreshAccountsSeconds.min,
      SETTINGS_LIMITS.refresh.autoRefreshAccountsSeconds.max,
      current.auto_refresh_accounts_seconds,
    ),
    scheduled_refresh_enabled: pickBoolean(
      defaults.scheduled_refresh_enabled ?? false,
      current.scheduled_refresh_enabled,
    ),
    scheduled_refresh_interval_minutes: normalizeInteger(
      defaults.scheduled_refresh_interval_minutes ?? 30,
      SETTINGS_LIMITS.refresh.scheduledRefreshIntervalMinutes.min,
      SETTINGS_LIMITS.refresh.scheduledRefreshIntervalMinutes.max,
      current.scheduled_refresh_interval_minutes,
    ),
    scheduled_refresh_cron: pickString(
      defaults.scheduled_refresh_cron ?? '',
      current.scheduled_refresh_cron,
    ),
    verification_code_resend_count: normalizeInteger(
      defaults.verification_code_resend_count ?? 2,
      SETTINGS_LIMITS.refresh.verificationCodeResendCount.min,
      SETTINGS_LIMITS.refresh.verificationCodeResendCount.max,
      current.verification_code_resend_count,
    ),
    refresh_batch_size: normalizeInteger(
      defaults.refresh_batch_size ?? 5,
      SETTINGS_LIMITS.refresh.refreshBatchSize.min,
      SETTINGS_LIMITS.refresh.refreshBatchSize.max,
      current.refresh_batch_size,
    ),
    refresh_batch_interval_minutes: normalizeInteger(
      defaults.refresh_batch_interval_minutes ?? 30,
      SETTINGS_LIMITS.refresh.refreshBatchIntervalMinutes.min,
      SETTINGS_LIMITS.refresh.refreshBatchIntervalMinutes.max,
      current.refresh_batch_interval_minutes,
    ),
    refresh_cooldown_hours: normalizeDecimal(
      defaults.refresh_cooldown_hours ?? 12,
      SETTINGS_LIMITS.refresh.refreshCooldownHours.min,
      SETTINGS_LIMITS.refresh.refreshCooldownHours.max,
      current.refresh_cooldown_hours,
    ),
    delete_expired_accounts: pickBoolean(
      defaults.delete_expired_accounts ?? false,
      current.delete_expired_accounts,
    ),
    auto_register_enabled: pickBoolean(
      defaults.auto_register_enabled ?? false,
      current.auto_register_enabled,
    ),
    min_account_count: normalizeInteger(
      defaults.min_account_count ?? 0,
      SETTINGS_LIMITS.refresh.minAccountCount.min,
      SETTINGS_LIMITS.refresh.minAccountCount.max,
      current.min_account_count,
    ),
    duckmail: {
      ...defaults.duckmail,
      ...current.duckmail,
      base_url: pickString(defaults.duckmail.base_url ?? '', current.duckmail?.base_url),
      api_key: pickString(defaults.duckmail.api_key ?? '', current.duckmail?.api_key),
      verify_ssl: pickBoolean(defaults.duckmail.verify_ssl ?? false, current.duckmail?.verify_ssl),
    },
    moemail: {
      ...defaults.moemail,
      ...current.moemail,
      base_url: pickString(defaults.moemail.base_url ?? '', current.moemail?.base_url),
      api_key: pickString(defaults.moemail.api_key ?? '', current.moemail?.api_key),
      domain: pickString(defaults.moemail.domain ?? '', current.moemail?.domain),
    },
    freemail: {
      ...defaults.freemail,
      ...current.freemail,
      base_url: pickString(defaults.freemail.base_url ?? '', current.freemail?.base_url),
      jwt_token: pickString(defaults.freemail.jwt_token ?? '', current.freemail?.jwt_token),
      verify_ssl: pickBoolean(defaults.freemail.verify_ssl ?? false, current.freemail?.verify_ssl),
      domain: pickString(defaults.freemail.domain ?? '', current.freemail?.domain),
    },
    gptmail: {
      ...defaults.gptmail,
      ...current.gptmail,
      base_url: pickString(defaults.gptmail.base_url ?? '', current.gptmail?.base_url),
      api_key: pickString(defaults.gptmail.api_key ?? '', current.gptmail?.api_key),
      verify_ssl: pickBoolean(defaults.gptmail.verify_ssl ?? false, current.gptmail?.verify_ssl),
      domain: pickString(defaults.gptmail.domain ?? '', current.gptmail?.domain),
    },
    cfmail: {
      ...defaults.cfmail,
      ...current.cfmail,
      base_url: pickString(defaults.cfmail.base_url ?? '', current.cfmail?.base_url),
      api_key: pickString(defaults.cfmail.api_key ?? '', current.cfmail?.api_key),
      verify_ssl: pickBoolean(defaults.cfmail.verify_ssl ?? false, current.cfmail?.verify_ssl),
      domain: pickString(defaults.cfmail.domain ?? '', current.cfmail?.domain),
    },
  }
}

export const syncRefreshMirrors = (payload: Settings) => {
  const refreshSettings = hydrateRefreshSettings(payload)
  const browserMode = normalizeBrowserMode(
    refreshSettings.browser_mode,
    refreshSettings.browser_headless,
  )

  refreshSettings.browser_mode = browserMode
  refreshSettings.browser_headless = browserMode === 'headless'
  payload.retry.rate_limit_cooldown_seconds = normalizeInteger(
    payload.retry.text_rate_limit_cooldown_seconds,
    SETTINGS_LIMITS.retry.textCooldownSeconds.min,
    SETTINGS_LIMITS.retry.textCooldownSeconds.max,
    payload.retry.text_rate_limit_cooldown_seconds,
  )
  payload.refresh_settings = refreshSettings
}
