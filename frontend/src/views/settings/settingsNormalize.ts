import type { Settings } from '@/types/settings'
import {
  normalizeImageOutputFormat,
  normalizeInteger,
  normalizeStringArray,
  normalizeVideoOutputFormat,
  pickBoolean,
  pickNumber,
  pickString,
} from './settingsHelpers'
import {
  createDefaultSettings,
  DEFAULT_BASIC_SETTINGS,
  DEFAULT_IMAGE_GENERATION_SETTINGS,
  DEFAULT_PUBLIC_DISPLAY_SETTINGS,
  DEFAULT_QUOTA_LIMITS_SETTINGS,
  DEFAULT_RETRY_SETTINGS,
  DEFAULT_SESSION_SETTINGS,
  DEFAULT_VIDEO_GENERATION_SETTINGS,
} from './settingsDefaults'
import { SETTINGS_LIMITS } from './settingsConstraints'
import { hydrateRefreshSettings } from './settingsRefresh'

export const normalizeSettings = (value: Settings | null | undefined): Settings => {
  const defaults = createDefaultSettings()
  const next = JSON.parse(JSON.stringify(value ?? defaults)) as Partial<Settings>

  const textRateLimitCooldownSeconds = pickNumber(
    DEFAULT_RETRY_SETTINGS.text_rate_limit_cooldown_seconds,
    next.retry?.text_rate_limit_cooldown_seconds,
    next.retry?.rate_limit_cooldown_seconds,
  )

  return {
    basic: {
      ...DEFAULT_BASIC_SETTINGS,
      ...next.basic,
      api_key: pickString(DEFAULT_BASIC_SETTINGS.api_key || '', next.basic?.api_key),
      base_url: pickString(DEFAULT_BASIC_SETTINGS.base_url || '', next.basic?.base_url),
      proxy_for_chat: pickString(
        DEFAULT_BASIC_SETTINGS.proxy_for_chat || '',
        next.basic?.proxy_for_chat,
      ),
      image_expire_hours: normalizeInteger(
        DEFAULT_BASIC_SETTINGS.image_expire_hours || 12,
        SETTINGS_LIMITS.basic.imageExpireHours.min,
        SETTINGS_LIMITS.basic.imageExpireHours.max,
        next.basic?.image_expire_hours,
      ),
    },
    retry: {
      ...DEFAULT_RETRY_SETTINGS,
      ...next.retry,
      max_account_switch_tries: normalizeInteger(
        DEFAULT_RETRY_SETTINGS.max_account_switch_tries,
        SETTINGS_LIMITS.retry.maxAccountSwitchTries.min,
        SETTINGS_LIMITS.retry.maxAccountSwitchTries.max,
        next.retry?.max_account_switch_tries,
      ),
      rate_limit_cooldown_seconds: normalizeInteger(
        DEFAULT_RETRY_SETTINGS.text_rate_limit_cooldown_seconds,
        SETTINGS_LIMITS.retry.textCooldownSeconds.min,
        SETTINGS_LIMITS.retry.textCooldownSeconds.max,
        textRateLimitCooldownSeconds,
      ),
      text_rate_limit_cooldown_seconds: normalizeInteger(
        DEFAULT_RETRY_SETTINGS.text_rate_limit_cooldown_seconds,
        SETTINGS_LIMITS.retry.textCooldownSeconds.min,
        SETTINGS_LIMITS.retry.textCooldownSeconds.max,
        textRateLimitCooldownSeconds,
      ),
      images_rate_limit_cooldown_seconds: normalizeInteger(
        DEFAULT_RETRY_SETTINGS.images_rate_limit_cooldown_seconds,
        SETTINGS_LIMITS.retry.imagesCooldownSeconds.min,
        SETTINGS_LIMITS.retry.imagesCooldownSeconds.max,
        next.retry?.images_rate_limit_cooldown_seconds,
      ),
      videos_rate_limit_cooldown_seconds: normalizeInteger(
        DEFAULT_RETRY_SETTINGS.videos_rate_limit_cooldown_seconds,
        SETTINGS_LIMITS.retry.videosCooldownSeconds.min,
        SETTINGS_LIMITS.retry.videosCooldownSeconds.max,
        next.retry?.videos_rate_limit_cooldown_seconds,
      ),
      session_cache_ttl_seconds: normalizeInteger(
        DEFAULT_RETRY_SETTINGS.session_cache_ttl_seconds,
        SETTINGS_LIMITS.retry.sessionCacheTtlSeconds.min,
        SETTINGS_LIMITS.retry.sessionCacheTtlSeconds.max,
        next.retry?.session_cache_ttl_seconds,
      ),
    },
    public_display: {
      ...DEFAULT_PUBLIC_DISPLAY_SETTINGS,
      ...next.public_display,
      logo_url: pickString(DEFAULT_PUBLIC_DISPLAY_SETTINGS.logo_url || '', next.public_display?.logo_url),
      chat_url: pickString(DEFAULT_PUBLIC_DISPLAY_SETTINGS.chat_url || '', next.public_display?.chat_url),
    },
    image_generation: {
      ...DEFAULT_IMAGE_GENERATION_SETTINGS,
      ...next.image_generation,
      enabled: pickBoolean(DEFAULT_IMAGE_GENERATION_SETTINGS.enabled, next.image_generation?.enabled),
      supported_models: normalizeStringArray(next.image_generation?.supported_models),
      output_format: normalizeImageOutputFormat(next.image_generation?.output_format),
    },
    video_generation: {
      ...DEFAULT_VIDEO_GENERATION_SETTINGS,
      ...next.video_generation,
      output_format: normalizeVideoOutputFormat(next.video_generation?.output_format),
    },
    session: {
      ...DEFAULT_SESSION_SETTINGS,
      ...next.session,
      expire_hours: normalizeInteger(
        DEFAULT_SESSION_SETTINGS.expire_hours,
        SETTINGS_LIMITS.session.expireHours.min,
        SETTINGS_LIMITS.session.expireHours.max,
        next.session?.expire_hours,
      ),
    },
    refresh_settings: hydrateRefreshSettings(next),
    quota_limits: {
      ...DEFAULT_QUOTA_LIMITS_SETTINGS,
      ...next.quota_limits,
      enabled: pickBoolean(DEFAULT_QUOTA_LIMITS_SETTINGS.enabled, next.quota_limits?.enabled),
      text_daily_limit: normalizeInteger(
        DEFAULT_QUOTA_LIMITS_SETTINGS.text_daily_limit,
        SETTINGS_LIMITS.quota.dailyLimit.min,
        SETTINGS_LIMITS.quota.dailyLimit.max,
        next.quota_limits?.text_daily_limit,
      ),
      images_daily_limit: normalizeInteger(
        DEFAULT_QUOTA_LIMITS_SETTINGS.images_daily_limit,
        SETTINGS_LIMITS.quota.dailyLimit.min,
        SETTINGS_LIMITS.quota.dailyLimit.max,
        next.quota_limits?.images_daily_limit,
      ),
      videos_daily_limit: normalizeInteger(
        DEFAULT_QUOTA_LIMITS_SETTINGS.videos_daily_limit,
        SETTINGS_LIMITS.quota.dailyLimit.min,
        SETTINGS_LIMITS.quota.dailyLimit.max,
        next.quota_limits?.videos_daily_limit,
      ),
    },
  }
}
