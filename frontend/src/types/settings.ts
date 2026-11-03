export type TempMailProvider = 'duckmail' | 'moemail' | 'freemail' | 'gptmail' | 'cfmail'

export type BrowserMode = 'normal' | 'silent' | 'headless'

export type ImageOutputFormat = 'base64' | 'url'

export type VideoOutputFormat = 'html' | 'url' | 'markdown'

export interface DuckmailSettings {
  base_url: string
  api_key: string
  verify_ssl: boolean
}

export interface MoemailSettings {
  base_url: string
  api_key: string
  domain: string
}

export interface FreemailSettings {
  base_url: string
  jwt_token: string
  verify_ssl: boolean
  domain: string
}

export interface GptmailSettings {
  base_url: string
  api_key: string
  verify_ssl: boolean
  domain: string
}

export interface CfmailSettings {
  base_url: string
  api_key: string
  verify_ssl: boolean
  domain: string
}

export interface RefreshSettings {
  proxy_for_auth: string
  duckmail: DuckmailSettings
  temp_mail_provider: TempMailProvider
  moemail: MoemailSettings
  freemail: FreemailSettings
  mail_proxy_enabled: boolean
  gptmail: GptmailSettings
  cfmail: CfmailSettings
  browser_mode: BrowserMode
  browser_headless: boolean
  refresh_window_hours: number
  register_domain: string
  register_default_count: number
  auto_refresh_accounts_seconds: number
  scheduled_refresh_enabled: boolean
  scheduled_refresh_interval_minutes: number
  scheduled_refresh_cron: string
  verification_code_resend_count: number
  refresh_batch_size: number
  refresh_batch_interval_minutes: number
  refresh_cooldown_hours: number
  delete_expired_accounts: boolean
  auto_register_enabled: boolean
  min_account_count: number
}

export interface Settings {
  basic: {
    api_key: string
    base_url: string
    proxy_for_chat: string
    image_expire_hours: number
  }
  retry: {
    max_account_switch_tries: number
    rate_limit_cooldown_seconds: number
    text_rate_limit_cooldown_seconds: number
    images_rate_limit_cooldown_seconds: number
    videos_rate_limit_cooldown_seconds: number
    session_cache_ttl_seconds: number
  }
  public_display: {
    logo_url: string
    chat_url: string
  }
  image_generation: {
    enabled: boolean
    supported_models: string[]
    output_format: ImageOutputFormat
  }
  video_generation: {
    output_format: VideoOutputFormat
  }
  session: {
    expire_hours: number
  }
  refresh_settings: RefreshSettings
  quota_limits: {
    enabled: boolean
    text_daily_limit: number
    images_daily_limit: number
    videos_daily_limit: number
  }
}
