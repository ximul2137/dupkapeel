<template>
  <div class="space-y-6">
    <section class="ui-panel">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p class="ui-section-title">Centrum pomocy</p>
          <p class="mt-1 text-xs text-muted-foreground">
            Szybki start, przykłady wywołań API, import kont oraz informacje o projekcie.
          </p>
        </div>
      </div>

      <div class="ui-segmented mt-6 text-xs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="ui-segmented-btn flex-1 justify-center px-4 py-2"
          :class="activeTab === tab.id ? 'ui-segmented-btn-active' : ''"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="mt-6 space-y-6 text-sm text-foreground">
        <div v-if="activeTab === 'api'" class="space-y-6">
          <div class="space-y-2">
            <p class="text-sm font-semibold">Format konfiguracji kont</p>
            <p class="mt-1 text-xs text-muted-foreground">
              Obsługuje plik <code>accounts.json</code>, zmienną <code>ACCOUNTS_CONFIG</code> oraz import JSON w panelu i przez <code>import_cookies.py</code>.
            </p>
            <pre class="mt-3 overflow-x-auto whitespace-pre-wrap rounded-2xl border border-border bg-card px-4 py-3 text-xs font-mono scrollbar-slim">[
  {
    "id": "account_1",
    "secure_c_ses": "CSE.Ad...",
    "csesidx": "498...",
    "config_id": "0cd...",
    "host_c_oses": "",
    "expires_at": "2026-12-31 23:59:59"
  }
]</pre>
            <p class="mt-2 text-xs text-muted-foreground">
              Wymagane: <code>secure_c_ses</code> / <code>csesidx</code> / <code>config_id</code>;
              <code>id</code>, <code>host_c_oses</code>, <code>expires_at</code> są opcjonalne.
            </p>
          </div>

          <div class="space-y-2">
            <p class="text-sm font-semibold">Przykład wywołania czatu (curl)</p>
            <p class="mt-1 text-xs text-muted-foreground">
              Standardowy format zgodny z OpenAI (obsługuje tryb strumieniowy, zwykły oraz narzędzia <code>tools</code>).
            </p>
            <pre class="mt-3 overflow-x-auto whitespace-pre-wrap rounded-2xl border border-border bg-card px-4 py-3 text-xs font-mono scrollbar-slim">curl -X POST "http://localhost:7860/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gemini-3.5-flash",
    "stream": false,
    "temperature": 0.7,
    "messages": [
      { "role": "system", "content": "Jesteś zwięzłym asystentem" },
      { "role": "user", "content": "Opisz krótko ten projekt" }
    ]
  }'</pre>
            <p class="mt-2 text-xs text-muted-foreground">
              Jeśli nie ustawiono klucza API, nagłówek <code>Authorization</code> można pominąć.
            </p>
          </div>

          <div class="space-y-2">
            <p class="text-sm font-semibold">Przykład generowania obrazu</p>
            <p class="mt-1 text-xs text-muted-foreground">
              Generowanie i edycja obrazów obsługują wejście URL / Base64; format wyjściowy zależy od ustawień.
            </p>
            <div class="mt-3 grid gap-3 md:grid-cols-2">
              <pre class="overflow-x-auto whitespace-pre-wrap rounded-2xl border border-border bg-card px-4 py-3 text-xs font-mono scrollbar-slim">curl -X POST "http://localhost:7860/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gemini-imagen",
    "stream": false,
    "messages": [
      { "role": "user", "content": "Wygeneruj kota w stylu cyberpunk" }
    ]
  }'</pre>
              <pre class="overflow-x-auto whitespace-pre-wrap rounded-2xl border border-border bg-card px-4 py-3 text-xs font-mono scrollbar-slim">curl -X POST "http://localhost:7860/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gemini-3.5-flash",
    "stream": false,
    "messages": [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "Zmień styl obrazu na ilustrację" },
          { "type": "image_url", "image_url": { "url": "https://example.com/cat.png" } }
        ]
      }
    ]
  }'</pre>
            </div>
          </div>

          <div class="space-y-2">
            <p class="text-sm font-semibold">Przykład generowania wideo</p>
            <p class="mt-1 text-xs text-muted-foreground">
              Model <code>gemini-veo</code> działa przez ten sam endpoint czatu.
            </p>
            <pre class="mt-3 overflow-x-auto whitespace-pre-wrap rounded-2xl border border-border bg-card px-4 py-3 text-xs font-mono scrollbar-slim">curl -X POST "http://localhost:7860/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "gemini-veo",
    "stream": true,
    "messages": [
      { "role": "user", "content": "Wygeneruj wideo z bawiącym się kotem" }
    ]
  }'</pre>
          </div>

          <div class="space-y-2">
            <p class="text-sm font-semibold">Najważniejsze endpointy</p>
            <div class="overflow-x-auto rounded-2xl border border-border bg-card">
              <table class="min-w-full text-left text-xs">
                <thead class="bg-muted/40 text-muted-foreground">
                  <tr>
                    <th class="px-4 py-3 font-medium">Endpoint</th>
                    <th class="px-4 py-3 font-medium">Method</th>
                    <th class="px-4 py-3 font-medium">Opis</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="endpoint in endpoints" :key="endpoint.path" class="border-t border-border">
                    <td class="px-4 py-3 font-mono text-[11px]">{{ endpoint.path }}</td>
                    <td class="px-4 py-3">{{ endpoint.method }}</td>
                    <td class="px-4 py-3 text-muted-foreground">{{ endpoint.description }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div v-else-if="activeTab === 'helper'" class="space-y-6">
          <div class="space-y-2">
            <p class="text-sm font-semibold">Import ciasteczek (Cookie-Editor + import_cookies.py)</p>
            <p class="mt-1 text-xs text-muted-foreground">
              Służy do szybkiego zaimportowania konta z przeglądarki do lokalnego serwera proxy.
            </p>
            <div class="grid gap-3 md:grid-cols-2">
              <div class="rounded-2xl border border-border bg-card p-4">
                <p class="font-medium text-foreground">Skrypt importu</p>
                <ul class="mt-3 space-y-2 text-xs text-muted-foreground">
                  <li>Skrypt w projekcie: <code>import_cookies.py</code></li>
                  <li>W Cookie-Editor kliknij <code>Export</code> → <code>JSON</code> i zapisz jako <code>business.gemini.google_cookies.json</code></li>
                  <li>Uruchom: <code>python import_cookies.py business.gemini.google_cookies.json "ADRES_URL"</code></li>
                </ul>
              </div>

              <div class="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <p class="font-medium text-amber-700">Wskazówki przed importem</p>
                <ol class="mt-3 space-y-2 text-xs leading-relaxed text-amber-800">
                  <li>1. Zalecana przeglądarka to <code>Firefox</code> (w Chrome/Edge sesja wygasa szybciej)</li>
                  <li>2. Eksport wykonaj na otwartej karcie <code>business.gemini.google</code></li>
                  <li>3. Adres URL musi zawierać zarówno <strong>/cid/</strong>, jak i <strong>csesidx=</strong></li>
                  <li>4. W pliku muszą znajdować się ciasteczka <code>__Secure-C_SES</code> oraz <code>__Host-C_OSES</code></li>
                </ol>
              </div>
            </div>
          </div>

          <div class="space-y-2">
            <p class="text-sm font-semibold">Kroki importu</p>
            <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <div v-for="step in helperSteps" :key="step.title" class="rounded-2xl border border-border bg-card p-4">
                <p class="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">{{ step.index }}</p>
                <p class="mt-2 text-sm font-medium text-foreground">{{ step.title }}</p>
                <p class="mt-2 text-xs leading-relaxed text-muted-foreground">{{ step.description }}</p>
              </div>
            </div>
          </div>

          <div class="space-y-2">
            <p class="text-sm font-semibold">Przykład JSON konta</p>
            <pre class="mt-3 overflow-x-auto whitespace-pre-wrap rounded-2xl border border-border bg-card px-4 py-3 text-xs font-mono scrollbar-slim">[
  {
    "id": "you@example.com",
    "secure_c_ses": "CSE.Ad...",
    "csesidx": "498...",
    "config_id": "0cd...",
    "host_c_oses": "",
    "expires_at": "2026-04-25 12:00:00"
  }
]</pre>
            <p class="mt-2 text-xs text-muted-foreground">
              Taki JSON możesz też wkleić bezpośrednio w zakładce Konta → Importuj konta.
            </p>
          </div>
        </div>

        <div v-else class="space-y-6">
          <div class="rounded-2xl border border-rose-200 bg-rose-50 p-4">
            <p class="font-medium text-rose-700">Informacje o wykorzystaniu</p>
            <p class="mt-2 text-xs leading-relaxed text-rose-700">
              Lokalny serwer proxy geminienterprise-grupkapeel udostępniający interfejs kompatybilny z OpenAI.
            </p>
          </div>

          <div class="grid gap-3 md:grid-cols-2">
            <div class="rounded-2xl border border-border bg-card p-4">
              <p class="font-medium text-foreground">Zastosowanie</p>
              <ul class="mt-3 space-y-2 text-xs leading-relaxed text-muted-foreground">
                <li>• Lokalna integracja z OpenCode i innymi klientami OpenAI API</li>
                <li>• Testowanie kompatybilności modeli oraz wywołań narzędzi (tool calls)</li>
                <li>• Nauka i zastosowania niekomercyjne</li>
              </ul>
            </div>

            <div class="rounded-2xl border border-border bg-card p-4">
              <p class="font-medium text-foreground">Pamiętaj o przestrzeganiu</p>
              <ul class="mt-3 space-y-2 text-xs leading-relaxed text-muted-foreground">
                <li>• Warunków korzystania z usług Google</li>
                <li>• Dodatkowych warunków Google Workspace / Gemini Enterprise</li>
                <li>• Zasad bezpieczeństwa własnej organizacji</li>
                <li>• Ochrony eksportowanych ciasteczek sesyjnych</li>
              </ul>
            </div>
          </div>

          <div class="rounded-2xl border border-border bg-card p-4">
            <p class="font-medium text-foreground">Dokumentacja lokalna</p>
            <p class="mt-2 text-xs text-muted-foreground">
              Pełna instrukcja znajduje się w plikach README.md oraz AGENTS.md w folderze projektu.
            </p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

type TabId = 'api' | 'helper' | 'disclaimer'

const activeTab = ref<TabId>('api')

const tabs: Array<{ id: TabId; label: string }> = [
  { id: 'api', label: 'Dokumentacja API' },
  { id: 'helper', label: 'Import konta' },
  { id: 'disclaimer', label: 'Informacje' },
]

const endpoints = [
  { path: '/v1/models', method: 'GET', description: 'Lista modeli' },
  { path: '/v1/chat/completions', method: 'POST', description: 'Czat / narzędzia / obrazy / wideo' },
  { path: '/v1/images/generations', method: 'POST', description: 'Generowanie obrazów' },
  { path: '/v1/images/edits', method: 'POST', description: 'Edycja obrazów' },
  { path: '/health', method: 'GET', description: 'Sprawdzenie stanu serwera' },
]

const helperSteps = [
  {
    index: 'STEP 1',
    title: 'Zainstaluj Cookie-Editor',
    description: 'Zainstaluj rozszerzenie Cookie-Editor w przeglądarce Firefox.',
  },
  {
    index: 'STEP 2',
    title: 'Otwórz czat',
    description: 'Zaloguj się na business.gemini.google i otwórz rozmowę.',
  },
  {
    index: 'STEP 3',
    title: 'Skopiuj URL i ciasteczka',
    description: 'Skopiuj pełny adres URL (z /cid/ i csesidx=) oraz wyeksportuj ciasteczka jako JSON.',
  },
  {
    index: 'STEP 4',
    title: 'Zaimportuj do proxy',
    description: 'Użyj skryptu import_cookies.py lub wklej JSON w zakładce Konta.',
  },
]
</script>
