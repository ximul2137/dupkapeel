<template>
  <div class="space-y-8">
    <section v-if="isLoading && !localSettings" class="ui-panel text-sm text-muted-foreground">
      Ładowanie ustawień...
    </section>

    <section v-else class="ui-panel">
      <PanelPageHeader
        title="Panel konfiguracji"
        description="Konfiguracja kluczowych parametrów serwera proxy, ponowień, limitów oraz generowania multimediów."
      >
        <template #actions>
          <Button
            size="xs"
            variant="primary"
            root-class="min-w-14 justify-center"
            :disabled="isSaving || !localSettings"
            @click="handleSave"
          >
            {{ isSaving ? 'Zapisywanie...' : 'Zapisz ustawienia' }}
          </Button>
        </template>
      </PanelPageHeader>

      <div
        v-if="errorMessage"
        class="mt-4 rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive"
      >
        {{ errorMessage }}
      </div>

      <div v-if="localSettings" class="mt-6 space-y-8">
        <div class="grid gap-4 lg:grid-cols-3">
          <div class="space-y-4">
            <div class="ui-card">
              <CardSectionHeader title="Podstawowe" />
              <div class="mt-4 space-y-3">
                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <label class="block">Klucz API</label>
                  <HelpTip text="Można podać wiele kluczy rozdzielonych przecinkami, np. key1,key2,key3" />
                </div>
                <Input
                  v-model="localSettings.basic.api_key"
                  type="text"
                  block
                  placeholder="Opcjonalny; wiele kluczy oddziel przecinkiem"
                />

                <label class="block text-xs text-muted-foreground">Adres bazowy (Base URL)</label>
                <Input
                  v-model="localSettings.basic.base_url"
                  type="text"
                  block
                  placeholder="Wykrywany automatycznie lub wpisz ręcznie"
                />

                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>Proxy dla czatu</span>
                  <HelpTip text="Używane dla zapytań JWT, sesji i wiadomości; pozostaw puste dla połączenia bezpośredniego." />
                </div>
                <Input
                  v-model="localSettings.basic.proxy_for_chat"
                  type="text"
                  block
                  placeholder="http://127.0.0.1:7890"
                />
              </div>
            </div>

            <div class="ui-card">
              <CardSectionHeader title="Ponawianie i chłodzenie" />
              <div class="mt-4 grid grid-cols-2 gap-3">
                <label class="col-span-2 text-xs text-muted-foreground">Liczba przełączeń konta</label>
                <Input
                  v-model="maxAccountSwitchTriesInput"
                  type="number"
                  block
                  root-class="col-span-2"
                />

                <label class="col-span-2 text-xs text-muted-foreground">Chłodzenie czatu (godz.)</label>
                <Input
                  v-model="textCooldownHoursInput"
                  type="number"
                  block
                  root-class="col-span-2"
                />

                <label class="col-span-2 text-xs text-muted-foreground">Chłodzenie obrazów (godz.)</label>
                <Input
                  v-model="imagesCooldownHoursInput"
                  type="number"
                  block
                  root-class="col-span-2"
                />

                <label class="col-span-2 text-xs text-muted-foreground">Chłodzenie wideo (godz.)</label>
                <Input
                  v-model="videosCooldownHoursInput"
                  type="number"
                  block
                  root-class="col-span-2"
                />

                <label class="col-span-2 text-xs text-muted-foreground">Czas bufora sesji (s)</label>
                <Input
                  v-model="sessionCacheTtlInput"
                  type="number"
                  block
                  root-class="col-span-2"
                />
              </div>
            </div>
          </div>

          <div class="space-y-4">
            <div class="ui-card">
              <CardSectionHeader
                title="Poczta i rejestracja"
                help-text="Ustawienia zewnętrznych usług tymczasowej poczty i automatycznego odświeżania."
              />

              <div class="mt-4 space-y-3">
                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>Proxy dla operacji na kontach</span>
                  <HelpTip text="Używane przy logowaniu i odświeżaniu kont oraz dla tymczasowej poczty." />
                </div>
                <Input
                  v-model="localSettings.refresh_settings.proxy_for_auth"
                  type="text"
                  block
                  placeholder="http://127.0.0.1:7890"
                />

                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>Tryb przeglądarki</span>
                  <HelpTip text="normal: zwykłe okno; silent: ciche okno; headless: w tle." />
                </div>
                <SelectMenu
                  v-model="localSettings.refresh_settings.browser_mode"
                  :options="browserModeOptions"
                  class="w-full"
                />

                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>Usługa tymczasowej poczty</span>
                  <HelpTip text="Wybierz dostawcę, aby wyświetlić jego opcje konfiguracji." />
                </div>
                <SelectMenu
                  v-model="localSettings.refresh_settings.temp_mail_provider"
                  :options="tempMailProviderOptions"
                  class="w-full"
                />

                <Checkbox v-model="localSettings.refresh_settings.mail_proxy_enabled">
                  Włącz proxy dla poczty (używa proxy operacji na kontach)
                </Checkbox>

                <template v-if="localSettings.refresh_settings.temp_mail_provider === 'duckmail'">
                  <Checkbox v-model="localSettings.refresh_settings.duckmail.verify_ssl">
                    Weryfikacja SSL DuckMail
                  </Checkbox>

                  <label class="block text-xs text-muted-foreground">Adres API DuckMail</label>
                  <Input
                    v-model="localSettings.refresh_settings.duckmail.base_url"
                    type="text"
                    block
                    placeholder="https://api.duckmail.sbs"
                  />

                  <label class="block text-xs text-muted-foreground">Klucz API DuckMail</label>
                  <Input
                    v-model="localSettings.refresh_settings.duckmail.api_key"
                    type="text"
                    block
                    placeholder="dk_xxx"
                  />

                  <label class="block text-xs text-muted-foreground">Domena DuckMail (zalecana)</label>
                  <Input
                    v-model="localSettings.refresh_settings.register_domain"
                    type="text"
                    block
                    placeholder="Pozostaw puste dla wyboru automatycznego"
                  />
                </template>

                <template v-if="localSettings.refresh_settings.temp_mail_provider === 'moemail'">
                  <label class="block text-xs text-muted-foreground">Adres API Moemail</label>
                  <Input
                    v-model="localSettings.refresh_settings.moemail.base_url"
                    type="text"
                    block
                    placeholder="https://moemail.nanohajimi.mom"
                  />

                  <label class="block text-xs text-muted-foreground">Klucz API Moemail</label>
                  <Input
                    v-model="localSettings.refresh_settings.moemail.api_key"
                    type="text"
                    block
                    placeholder="X-API-Key"
                  />

                  <label class="block text-xs text-muted-foreground">Domena Moemail (opcjonalna)</label>
                  <Input
                    v-model="localSettings.refresh_settings.moemail.domain"
                    type="text"
                    block
                    placeholder="Pozostaw puste dla losowej"
                  />
                </template>

                <template v-if="localSettings.refresh_settings.temp_mail_provider === 'freemail'">
                  <Checkbox v-model="localSettings.refresh_settings.freemail.verify_ssl">
                    Weryfikacja SSL Freemail
                  </Checkbox>

                  <label class="block text-xs text-muted-foreground">Adres API Freemail</label>
                  <Input
                    v-model="localSettings.refresh_settings.freemail.base_url"
                    type="text"
                    block
                    placeholder="http://your-freemail-server.com"
                  />

                  <label class="block text-xs text-muted-foreground">Freemail JWT Token</label>
                  <Input
                    v-model="localSettings.refresh_settings.freemail.jwt_token"
                    type="text"
                    block
                    placeholder="eyJ..."
                  />

                  <label class="block text-xs text-muted-foreground">Domena Freemail (opcjonalna)</label>
                  <Input
                    v-model="localSettings.refresh_settings.freemail.domain"
                    type="text"
                    block
                    placeholder="Pozostaw puste dla losowej"
                  />
                </template>

                <template v-if="localSettings.refresh_settings.temp_mail_provider === 'gptmail'">
                  <Checkbox v-model="localSettings.refresh_settings.gptmail.verify_ssl">
                    Weryfikacja SSL GPTMail
                  </Checkbox>

                  <label class="block text-xs text-muted-foreground">Adres API GPTMail</label>
                  <Input
                    v-model="localSettings.refresh_settings.gptmail.base_url"
                    type="text"
                    block
                    placeholder="https://mail.chatgpt.org.uk"
                  />

                  <label class="block text-xs text-muted-foreground">Klucz API GPTMail</label>
                  <Input
                    v-model="localSettings.refresh_settings.gptmail.api_key"
                    type="text"
                    block
                    placeholder="X-API-Key"
                  />

                  <label class="block text-xs text-muted-foreground">Domena GPTMail (opcjonalna)</label>
                  <Input
                    v-model="localSettings.refresh_settings.gptmail.domain"
                    type="text"
                    block
                    placeholder="Pozostaw puste dla losowej"
                  />
                </template>

                <template v-if="localSettings.refresh_settings.temp_mail_provider === 'cfmail'">
                  <Checkbox v-model="localSettings.refresh_settings.cfmail.verify_ssl">
                    Weryfikacja SSL Cloudflare Mail
                  </Checkbox>

                  <label class="block text-xs text-muted-foreground">Adres API Cloudflare Mail</label>
                  <Input
                    v-model="localSettings.refresh_settings.cfmail.base_url"
                    type="text"
                    block
                    placeholder="https://your-cfmail-instance.example.com"
                  />

                  <label class="block text-xs text-muted-foreground">Hasło dostępu (opcjonalne)</label>
                  <Input
                    v-model="localSettings.refresh_settings.cfmail.api_key"
                    type="text"
                    block
                    placeholder="Pozostaw puste, jeśli brak hasła"
                  />

                  <label class="block text-xs text-muted-foreground">Domena poczty (opcjonalna)</label>
                  <Input
                    v-model="localSettings.refresh_settings.cfmail.domain"
                    type="text"
                    block
                    placeholder="Pozostaw puste dla losowej"
                  />
                </template>

                <label class="block text-xs text-muted-foreground">Domyślna liczba rejestracji</label>
                <Input
                  v-model="registerDefaultCountInput"
                  type="number"
                  block
                />
              </div>
            </div>

            <div class="ui-card">
              <CardSectionHeader title="Harmonogram odświeżania" />
              <div class="mt-4 space-y-3">
                <Checkbox v-model="localSettings.refresh_settings.auto_register_enabled">
                  Włącz automatyczne uzupełnianie kont
                </Checkbox>

                <Checkbox v-model="localSettings.refresh_settings.delete_expired_accounts">
                  Automatycznie usuwaj wygasłe konta
                </Checkbox>

                <label class="block text-xs text-muted-foreground">Minimalna liczba kont</label>
                <Input
                  v-model="minAccountCountInput"
                  type="number"
                  block
                />

                <label class="block text-xs text-muted-foreground">Okno odświeżania (godz.)</label>
                <Input
                  v-model="refreshWindowHoursInput"
                  type="number"
                  block
                />

                <label class="block text-xs text-muted-foreground">Interwał przeładowania listy kont (s)</label>
                <Input
                  v-model="autoRefreshAccountsSecondsInput"
                  type="number"
                  block
                />

                <Checkbox v-model="localSettings.refresh_settings.scheduled_refresh_enabled">
                  Włącz cykliczne odświeżanie
                </Checkbox>

                <label class="block text-xs text-muted-foreground">Interwał sprawdzania (min)</label>
                <Input
                  v-model="scheduledRefreshIntervalMinutesInput"
                  type="number"
                  block
                />

                <label class="block text-xs text-muted-foreground">Wyrażenie harmonogramu</label>
                <Input
                  v-model="localSettings.refresh_settings.scheduled_refresh_cron"
                  type="text"
                  block
                  placeholder="08:00,20:00 lub */120"
                />

                <label class="block text-xs text-muted-foreground">Liczba ponowień kodu weryfikacyjnego</label>
                <Input
                  v-model="verificationCodeResendCountInput"
                  type="number"
                  block
                />

                <label class="block text-xs text-muted-foreground">Rozmiar pojedynczej partii</label>
                <Input
                  v-model="refreshBatchSizeInput"
                  type="number"
                  block
                />

                <label class="block text-xs text-muted-foreground">Odstęp między partiami (min)</label>
                <Input
                  v-model="refreshBatchIntervalMinutesInput"
                  type="number"
                  block
                />

                <label class="block text-xs text-muted-foreground">Chłodzenie odświeżania (godz.)</label>
                <Input
                  v-model="refreshCooldownHoursInput"
                  type="number"
                  block
                />
              </div>
            </div>
          </div>

          <div class="space-y-4">
            <div class="ui-card">
              <CardSectionHeader
                title="Generowanie obrazów"
                help-text="Konfiguracja generowania obrazów i obsługiwanych modeli."
              />
              <div class="mt-4 space-y-3">
                <Checkbox v-model="localSettings.image_generation.enabled">
                  Włącz generowanie obrazów
                </Checkbox>

                <label class="block text-xs text-muted-foreground">Format wyjściowy</label>
                <SelectMenu
                  v-model="localSettings.image_generation.output_format"
                  :options="imageOutputOptions"
                  placement="up"
                  class="w-full"
                />

                <label class="block text-xs text-muted-foreground">Obsługiwane modele</label>
                <SelectMenu
                  v-model="localSettings.image_generation.supported_models"
                  :options="imageModelOptions"
                  placeholder="Wybierz modele"
                  placement="up"
                  multiple
                  class="w-full"
                />
              </div>
            </div>

            <div class="ui-card">
              <CardSectionHeader title="Generowanie wideo" />
              <div class="mt-4 space-y-3">
                <label class="block text-xs text-muted-foreground">Format wyjściowy</label>
                <SelectMenu
                  v-model="localSettings.video_generation.output_format"
                  :options="videoOutputOptions"
                  placement="up"
                  class="w-full"
                />
              </div>
            </div>

            <div class="ui-card">
              <CardSectionHeader
                title="Dzienne limity"
                help-text="Po osiągnięciu limitu następuje przełączenie konta. 0 oznacza brak limitu."
              />
              <div class="mt-4 space-y-3">
                <Checkbox v-model="localSettings.quota_limits.enabled">
                  Włącz aktywne zliczanie limitów
                </Checkbox>

                <label class="block text-xs text-muted-foreground">Dzienny limit czatu</label>
                <Input
                  v-model="quotaTextDailyLimitInput"
                  type="number"
                  block
                  placeholder="120"
                />

                <label class="block text-xs text-muted-foreground">Dzienny limit obrazów</label>
                <Input
                  v-model="quotaImagesDailyLimitInput"
                  type="number"
                  block
                  placeholder="2"
                />

                <label class="block text-xs text-muted-foreground">Dzienny limit wideo</label>
                <Input
                  v-model="quotaVideosDailyLimitInput"
                  type="number"
                  block
                  placeholder="1"
                />
              </div>
            </div>

            <div class="ui-card">
              <CardSectionHeader title="Strony publiczne" />
              <div class="mt-4 space-y-3">
                <label class="block text-xs text-muted-foreground">Adres logo</label>
                <Input
                  v-model="localSettings.public_display.logo_url"
                  type="text"
                  block
                  placeholder="Adres URL logo"
                />

                <label class="block text-xs text-muted-foreground">Adres czatu</label>
                <Input
                  v-model="localSettings.public_display.chat_url"
                  type="text"
                  block
                  placeholder="Adres URL czatu"
                />

                <label class="block text-xs text-muted-foreground">Czas ważności sesji (godz.)</label>
                <Input
                  v-model="sessionExpireHoursInput"
                  type="number"
                  block
                />
              </div>
            </div>

          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { Button, Checkbox, HelpTip, Input, SelectMenu } from 'nanocat-ui'
import CardSectionHeader from '@/components/ui/CardSectionHeader.vue'
import PanelPageHeader from '@/components/ui/PanelPageHeader.vue'
import { useSettingsPage } from './settings/useSettingsPage'

const {
  browserModeOptions,
  tempMailProviderOptions,
  imageOutputOptions,
  videoOutputOptions,
  imageModelOptions,
  isLoading,
  localSettings,
  isSaving,
  errorMessage,
  maxAccountSwitchTriesInput,
  textCooldownHoursInput,
  imagesCooldownHoursInput,
  videosCooldownHoursInput,
  sessionCacheTtlInput,
  registerDefaultCountInput,
  refreshWindowHoursInput,
  autoRefreshAccountsSecondsInput,
  scheduledRefreshIntervalMinutesInput,
  verificationCodeResendCountInput,
  refreshBatchSizeInput,
  refreshBatchIntervalMinutesInput,
  refreshCooldownHoursInput,
  minAccountCountInput,
  quotaTextDailyLimitInput,
  quotaImagesDailyLimitInput,
  quotaVideosDailyLimitInput,
  sessionExpireHoursInput,
  handleSave,
} = useSettingsPage()
</script>
