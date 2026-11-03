export const SETTINGS_LIMITS = {
  basic: {
    imageExpireHours: { min: -1, max: 720 },
  },
  retry: {
    maxAccountSwitchTries: { min: 1, max: 20 },
    textCooldownSeconds: { min: 3600, max: 86400 },
    imagesCooldownSeconds: { min: 3600, max: 86400 },
    videosCooldownSeconds: { min: 3600, max: 86400 },
    sessionCacheTtlSeconds: { min: 0, max: 86400 },
  },
  refresh: {
    refreshWindowHours: { min: 0, max: 24 },
    registerDefaultCount: { min: 1, max: 200 },
    autoRefreshAccountsSeconds: { min: 0, max: 86400 },
    scheduledRefreshIntervalMinutes: { min: 0, max: 720 },
    verificationCodeResendCount: { min: 0, max: 5 },
    refreshBatchSize: { min: 1, max: 50 },
    refreshBatchIntervalMinutes: { min: 0, max: 720 },
    refreshCooldownHours: { min: 0, max: 168 },
    minAccountCount: { min: 0, max: 1000 },
  },
  quota: {
    dailyLimit: { min: 0, max: 999999 },
  },
  session: {
    expireHours: { min: 1, max: 168 },
  },
} as const

