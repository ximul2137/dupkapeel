import type {
  BrowserMode,
  ImageOutputFormat,
  TempMailProvider,
  VideoOutputFormat,
} from '@/types/settings'
import { DEFAULT_RETRY_SETTINGS } from './settingsDefaults'

export const DEFAULT_COOLDOWN_HOURS = {
  text: DEFAULT_RETRY_SETTINGS.text_rate_limit_cooldown_seconds / 3600,
  images: DEFAULT_RETRY_SETTINGS.images_rate_limit_cooldown_seconds / 3600,
  videos: DEFAULT_RETRY_SETTINGS.videos_rate_limit_cooldown_seconds / 3600,
} as const

export const browserModeOptions = [
  { label: 'normal - zwykłe okno', value: 'normal' },
  { label: 'silent - ciche okno', value: 'silent' },
  { label: 'headless - w tle', value: 'headless' },
] satisfies Array<{ label: string; value: BrowserMode }>

export const tempMailProviderOptions = [
  { label: 'DuckMail', value: 'duckmail' },
  { label: 'Moemail', value: 'moemail' },
  { label: 'Freemail', value: 'freemail' },
  { label: 'GPTMail', value: 'gptmail' },
  { label: 'Cloudflare Mail', value: 'cfmail' },
] satisfies Array<{ label: string; value: TempMailProvider }>

export const imageOutputOptions = [
  { label: 'Kodowanie Base64', value: 'base64' },
  { label: 'Link URL', value: 'url' },
] satisfies Array<{ label: string; value: ImageOutputFormat }>

export const videoOutputOptions = [
  { label: 'Znacznik HTML video', value: 'html' },
  { label: 'Link URL', value: 'url' },
  { label: 'Format Markdown', value: 'markdown' },
] satisfies Array<{ label: string; value: VideoOutputFormat }>
