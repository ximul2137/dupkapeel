<template>
  <div class="relative space-y-8">
    <section class="ui-panel space-y-5">
      <ToolbarShell stack-on-mobile start-class="flex-1" end-class="xl:justify-end">
        <template #start>
          <div class="flex flex-wrap items-center gap-2.5">
            <Input
              :model-value="searchQuery"
              type="text"
              placeholder="Szukaj ID konta"
              block
              root-class="min-w-[11rem] flex-1 md:w-80 md:flex-none"
              @update:model-value="searchQuery = $event.trim()"
            />
            <FilterSelect
              v-model="statusFilter"
              :options="statusOptions"
              placeholder="Filtr statusu"
              aria-label="Filtr statusu kont"
            />
            <Button
              size="sm"
              variant="outline"
              root-class="shrink-0 whitespace-nowrap"
              :disabled="isLoading"
              @click="refreshAccounts"
            >
              Odśwież listę
            </Button>
            <Button
              size="sm"
              variant="outline"
              root-class="shrink-0 whitespace-nowrap"
              @click="openImportModal"
            >
              Importuj konta
            </Button>
            <Button
              size="sm"
              variant="outline"
              root-class="shrink-0 whitespace-nowrap"
              @click="openExportModal"
            >
              Eksportuj konta
            </Button>
            <Button
              size="sm"
              variant="outline"
              root-class="shrink-0 whitespace-nowrap"
              @click="openConfigPanel"
            >
              Konfiguracja kont
            </Button>
          </div>
        </template>
      </ToolbarShell>

      <div class="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div class="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <TriStateCheckbox
            :state="selectionState"
            :disabled="isSelectingAll || isLoading || filteredAccounts.length === 0"
            label="Zaznacz wszystkie"
            aria-label="Przełącz zaznaczenie wszystkich kont"
            @toggle="toggleSelectAll"
          />
          <Checkbox class="hidden" :model-value="allSelected" @update:model-value="toggleSelectAll">
            Zaznacz wyniki
          </Checkbox>
          <span class="rounded-full border border-border bg-muted/30 px-3 py-1.5">
            Kont łącznie: {{ filteredAccounts.length }}
          </span>
          <span class="rounded-full border border-border bg-muted/30 px-3 py-1.5">
            Zaznaczono: {{ selectedCount }}
          </span>
          <span
            v-if="selectionHint"
            class="rounded-full border border-primary/20 bg-primary/5 px-3 py-1.5 text-primary"
          >
            {{ selectionHint }}
          </span>
          <span
            v-if="batchProgress"
            class="rounded-full border border-border bg-muted/30 px-3 py-1.5"
          >
            Przetwarzanie {{ batchProgress.current }}/{{ batchProgress.total }}
          </span>
        </div>

        <div class="flex items-center gap-2">
          <button
            class="flex h-8 w-8 items-center justify-center rounded-full border transition-colors"
            :class="viewMode === 'table'
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground'"
            title="Widok listy"
            aria-label="Widok listy"
            @click="viewMode = 'table'"
          >
            <svg viewBox="0 0 20 20" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round">
              <path d="M4 5.5h12" />
              <path d="M4 10h12" />
              <path d="M4 14.5h12" />
            </svg>
          </button>
          <button
            class="flex h-8 w-8 items-center justify-center rounded-full border transition-colors"
            :class="viewMode === 'card'
              ? 'border-primary bg-primary/10 text-primary'
              : 'border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground'"
            title="Widok kart"
            aria-label="Widok kart"
            @click="viewMode = 'card'"
          >
            <svg viewBox="0 0 20 20" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3.5" y="3.5" width="5.5" height="5.5" rx="1" />
              <rect x="11" y="3.5" width="5.5" height="5.5" rx="1" />
              <rect x="3.5" y="11" width="5.5" height="5.5" rx="1" />
              <rect x="11" y="11" width="5.5" height="5.5" rx="1" />
            </svg>
          </button>
        </div>
      </div>

      <div
        v-if="isLoading && !filteredAccounts.length"
        class="rounded-2xl border border-border bg-background px-4 py-8 text-center text-sm text-muted-foreground"
      >
        Ładowanie kont...
      </div>

      <div
        v-else-if="viewMode === 'card'"
        class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3"
      >
        <div
          v-if="!filteredAccounts.length && !isLoading"
          class="col-span-full"
        >
          <EmptyState
            plain
            title="Brak kont"
            description="Zaimportuj konto, aby móc je włączać, wyłączać i eksportować."
          />
        </div>

        <div
          v-for="account in paginatedAccounts"
          :key="account.id"
          class="ui-card cursor-pointer transition-colors"
          :class="[rowClass(account), selectedIds.has(account.id) ? 'ring-2 ring-primary/20' : '']"
          @click="toggleSelect(account.id)"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-xs text-muted-foreground">ID konta</p>
              <p class="mt-1 font-mono text-xs text-foreground">{{ account.id }}</p>
            </div>
            <Checkbox
              :model-value="selectedIds.has(account.id)"
              @update:model-value="toggleSelect(account.id, $event)"
              @click.stop
            />
          </div>

          <div class="mt-4 grid grid-cols-2 gap-3 text-xs text-muted-foreground">
            <div>
              <p>Status</p>
              <p class="mt-1 flex flex-wrap items-center gap-1.5 text-sm font-semibold text-foreground">
                <span
                  class="inline-flex items-center rounded-full border border-border px-2 py-0.5 text-xs"
                  :class="statusClass(account)"
                >
                  {{ statusLabel(account) }}
                </span>
                <span
                  v-if="account.trial_days_remaining != null"
                  class="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-xs font-medium"
                  :class="trialBadgeClass(account.trial_days_remaining)"
                >
                  {{ account.trial_days_remaining }} dni
                </span>
              </p>
            </div>
            <div>
              <p>Pozostały czas</p>
              <p class="mt-1 text-sm font-semibold" :class="remainingClass(account)">
                {{ displayRemaining(account.remaining_display) }}
              </p>
              <p v-if="account.expires_at" class="mt-1 text-[11px]">
                {{ account.expires_at }}
              </p>
            </div>
            <div>
              <p>Limity</p>
              <div class="mt-1">
                <QuotaBadge v-if="account.quota_status" :quota-status="account.quota_status" />
                <span v-else class="text-xs text-muted-foreground">-</span>
              </div>
            </div>
            <div>
              <p>Błędy</p>
              <p class="mt-1 text-sm font-semibold text-foreground">{{ account.failure_count }}</p>
            </div>
            <div>
              <p>Sukcesy</p>
              <p class="mt-1 text-sm font-semibold text-foreground">{{ account.conversation_count }}</p>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap items-center gap-2">
            <Button size="xs" variant="outline" @click.stop="openEdit(account.id)">Edytuj</Button>
            <Button
              v-if="shouldShowEnable(account)"
              size="xs"
              variant="outline"
              @click.stop="handleEnable(account.id)"
            >
              Włącz
            </Button>
            <Button
              v-else-if="shouldShowDisable(account)"
              size="xs"
              variant="outline"
              @click.stop="handleDisable(account.id)"
            >
              Wyłącz
            </Button>
            <Button size="xs" variant="danger" @click.stop="handleDelete(account.id)">Usuń</Button>
          </div>
        </div>

      </div>

      <div v-else class="scrollbar-slim overflow-x-auto">
        <table class="min-w-full text-left text-sm">
          <thead class="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            <tr>
              <th class="py-3 pr-4">
                <TriStateCheckbox
                  :state="selectionState"
                  :disabled="isSelectingAll || isLoading || paginatedAccounts.length === 0"
                  aria-label="Zaznacz konto"
                  @toggle="toggleSelectAll"
                />
              </th>
              <th class="py-3 pr-6">ID konta</th>
              <th class="py-3 pr-6">Status</th>
              <th class="py-3 pr-6">Pozostało / wygasa</th>
              <th class="py-3 pr-6">Limity</th>
              <th class="py-3 pr-6">Błędy</th>
              <th class="py-3 pr-6">Sukcesy</th>
              <th class="py-3 text-right">Akcje</th>
            </tr>
          </thead>
          <tbody class="text-sm text-foreground">
            <tr v-if="!filteredAccounts.length && !isLoading">
              <td colspan="8" class="py-8">
                <EmptyState
                  plain
                  title="Brak kont"
                  description="Zaimportuj konto, aby móc je włączać, wyłączać i eksportować."
                />
              </td>
            </tr>
            <tr
              v-for="account in paginatedAccounts"
              :key="account.id"
              class="border-t border-border"
              :class="[rowClass(account), selectedIds.has(account.id) ? 'bg-primary/5' : '']"
              @click="toggleSelect(account.id)"
            >
              <td class="py-4 pr-4" @click.stop>
                <Checkbox
                  :model-value="selectedIds.has(account.id)"
                  @update:model-value="toggleSelect(account.id, $event)"
                />
              </td>
              <td class="py-4 pr-6 font-mono text-xs text-foreground">
                {{ account.id }}
              </td>
              <td class="py-4 pr-6">
                <div class="flex flex-wrap items-center gap-1.5">
                  <span
                    class="inline-flex items-center rounded-full border border-border px-3 py-1 text-xs"
                    :class="statusClass(account)"
                  >
                    {{ statusLabel(account) }}
                  </span>
                  <span
                    v-if="account.trial_days_remaining != null"
                    class="inline-flex items-center rounded-full border border-border px-2 py-1 text-xs font-medium"
                    :class="trialBadgeClass(account.trial_days_remaining)"
                  >
                    {{ account.trial_days_remaining }} dni
                  </span>
                </div>
              </td>
              <td class="py-4 pr-6">
                <div class="text-sm font-semibold" :class="remainingClass(account)">
                  {{ displayRemaining(account.remaining_display) }}
                </div>
                <span v-if="account.expires_at" class="block text-[11px] text-muted-foreground">
                  {{ account.expires_at }}
                </span>
              </td>
              <td class="py-4 pr-6">
                <QuotaBadge v-if="account.quota_status" :quota-status="account.quota_status" />
                <span v-else class="text-xs text-muted-foreground">-</span>
              </td>
              <td class="py-4 pr-6 text-xs text-muted-foreground">
                {{ account.failure_count }}
              </td>
              <td class="py-4 pr-6 text-xs text-muted-foreground">
                {{ account.conversation_count }}
              </td>
              <td class="py-4 text-right">
                <div class="flex flex-wrap items-center justify-end gap-2">
                  <Button size="xs" variant="outline" @click.stop="openEdit(account.id)">Edytuj</Button>
                  <Button
                    v-if="shouldShowEnable(account)"
                    size="xs"
                    variant="outline"
                    @click.stop="handleEnable(account.id)"
                  >
                    Włącz
                  </Button>
                  <Button
                    v-else-if="shouldShowDisable(account)"
                    size="xs"
                    variant="outline"
                    @click.stop="handleDisable(account.id)"
                  >
                    Wyłącz
                  </Button>
                  <Button size="xs" variant="danger" @click.stop="handleDelete(account.id)">Usuń</Button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex flex-col gap-3 border-t border-border/60 pt-4 md:flex-row md:items-center md:justify-between">
        <div class="text-xs text-muted-foreground">
          Wyświetlono {{ paginatedAccounts.length }} z {{ filteredAccounts.length }}
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs text-muted-foreground">Na stronę</span>
          <div class="w-[110px] shrink-0">
            <SelectMenu v-model="pageSize" :options="pageSizeOptions" placement="up" />
          </div>
          <Button size="sm" variant="outline" :disabled="currentPage === 1" @click="currentPage--">
            Poprzednia
          </Button>
          <span class="text-sm text-muted-foreground">{{ currentPage }} / {{ totalPages }}</span>
          <Button size="sm" variant="outline" :disabled="currentPage === totalPages" @click="currentPage++">
            Następna
          </Button>
        </div>
      </div>
    </section>

    <AccountBulkBar
      :selected-count="selectedCount"
      :busy="isOperating"
      :progress-label="batchProgressLabel"
      :items="batchMenuItems"
      @select="handleBatchAction"
      @clear="clearSelection"
    />
    <input
      ref="importFileInput"
      type="file"
      accept=".json,.txt,text/plain,application/json"
      class="hidden"
      @change="handleImportFile"
    />

    <ModalShell
      :open="isImportOpen"
      size-class="max-w-2xl"
      body-class="p-0"
      panel-class="overflow-hidden"
      :show-close="false"
      @close="closeImportModal"
    >
      <div class="flex max-h-[90vh] flex-col overflow-hidden">
          <ModalSectionHeader>
            <div>
              <p class="text-sm font-medium text-foreground">Import kont</p>
              <p class="mt-1 text-xs text-muted-foreground">
                Obsługuje plik JSON oraz import tekstowy wiersz po wierszu.
              </p>
            </div>
            <template #actions>
              <Button size="xs" variant="outline" root-class="min-w-14 justify-center" @click="closeImportModal">
              Zamknij
              </Button>
            </template>
          </ModalSectionHeader>

          <div class="scrollbar-slim flex-1 space-y-4 overflow-y-auto px-6 py-5">
            <div class="flex flex-wrap items-center gap-3">
              <Button size="sm" variant="outline" @click="triggerImportFile">
                Wybierz plik
              </Button>
              <span class="text-xs text-muted-foreground">
                {{ importFileName || 'Nie wybrano pliku — możesz wkleić zawartość poniżej' }}
              </span>
            </div>

            <textarea
              v-model="importText"
              rows="14"
              class="ui-textarea-sm min-h-[18rem] font-mono"
              :placeholder="importTextareaPlaceholder"
            ></textarea>

            <div class="rounded-2xl border border-border/70 bg-muted/20 px-4 py-3 text-xs text-muted-foreground">
              <p class="font-medium text-foreground">Obsługiwane formaty importu</p>
              <ul class="mt-2 list-disc space-y-1.5 pl-4">
                <li v-for="tip in importFormatTips" :key="tip">
                  {{ tip }}
                </li>
              </ul>
            </div>

            <div
              v-if="importError"
              class="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {{ importError }}
            </div>
          </div>

          <div class="flex items-center justify-end gap-2 border-t border-border/60 px-6 py-4">
            <Button size="sm" variant="outline" @click="closeImportModal">Anuluj</Button>
            <Button size="sm" variant="primary" :disabled="isImporting" @click="handleImportSubmit">
              {{ isImporting ? 'Importowanie...' : 'Importuj' }}
            </Button>
          </div>
      </div>
    </ModalShell>

    <ModalShell
      :open="isExportOpen"
      size-class="max-w-lg"
      body-class="p-0"
      panel-class="overflow-hidden"
      :show-close="false"
      @close="closeExportModal"
    >
      <div class="overflow-hidden">
          <ModalSectionHeader>
            <div>
              <p class="text-sm font-medium text-foreground">Eksport kont</p>
              <p class="mt-1 text-xs text-muted-foreground">Możesz wyeksportować wszystkie konta lub tylko zaznaczone.</p>
            </div>
            <template #actions>
              <Button size="xs" variant="outline" root-class="min-w-14 justify-center" @click="closeExportModal">
              Zamknij
            </Button>
            </template>
          </ModalSectionHeader>

          <div class="space-y-4 px-6 py-5">
            <div>
              <label class="block text-xs text-muted-foreground">Zakres eksportu</label>
              <div class="mt-2">
                <SelectMenu v-model="exportScope" :options="exportScopeOptions" class="w-full" />
              </div>
            </div>
            <div>
              <label class="block text-xs text-muted-foreground">Format eksportu</label>
              <div class="mt-2">
                <SelectMenu v-model="exportFormat" :options="exportFormatOptions" class="w-full" />
              </div>
            </div>
          </div>

          <div class="flex items-center justify-end gap-2 border-t border-border/60 px-6 py-4">
            <Button size="sm" variant="outline" @click="closeExportModal">Anuluj</Button>
            <Button size="sm" variant="primary" @click="runExport">Eksportuj</Button>
          </div>
      </div>
    </ModalShell>

    <ModalShell
      :open="isConfigOpen"
      size-class="max-w-4xl"
      body-class="p-0"
      panel-class="overflow-hidden"
      :show-close="false"
      @close="closeConfigPanel"
    >
      <div class="flex max-h-[92vh] flex-col overflow-hidden">
          <ModalSectionHeader>
            <div>
              <p class="text-sm font-medium text-foreground">Konfiguracja kont</p>
              <p class="mt-1 text-xs text-muted-foreground">Bezpośrednia edycja pełnego JSON. Przed zapisem przełącz na jawny tekst.</p>
            </div>
            <template #actions>
              <Button size="xs" variant="outline" @click="toggleConfigMask">
                {{ configMasked ? 'Pokaż jawny tekst' : 'Ukryj sekrety' }}
              </Button>
              <Button size="xs" variant="outline" root-class="min-w-14 justify-center" @click="closeConfigPanel">
                Zamknij
              </Button>
            </template>
          </ModalSectionHeader>

          <div class="scrollbar-slim flex-1 space-y-4 overflow-y-auto px-6 py-5">
            <textarea
              v-model="configJson"
              rows="20"
              class="ui-textarea-sm min-h-[26rem] font-mono"
            ></textarea>

            <div
              v-if="configError"
              class="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {{ configError }}
            </div>
          </div>

          <div class="flex items-center justify-end gap-2 border-t border-border/60 px-6 py-4">
            <Button size="sm" variant="outline" @click="closeConfigPanel">Anuluj</Button>
            <Button size="sm" variant="primary" :disabled="isOperating" @click="saveConfigPanel">
              Zapisz konfigurację
            </Button>
          </div>
      </div>
    </ModalShell>

    <ModalShell
      :open="isEditOpen"
      size-class="max-w-2xl"
      body-class="p-0"
      panel-class="overflow-hidden"
      :show-close="false"
      @close="closeEdit"
    >
      <div class="overflow-hidden">
          <ModalSectionHeader>
            <div>
              <p class="text-sm font-medium text-foreground">Edytuj konto</p>
              <p class="mt-1 text-xs text-muted-foreground">Zmień ciasteczka i parametry wybranego konta.</p>
            </div>
            <template #actions>
              <Button size="xs" variant="outline" root-class="min-w-14 justify-center" @click="closeEdit">
              Zamknij
              </Button>
            </template>
          </ModalSectionHeader>

          <div class="space-y-4 px-6 py-5">
            <FieldGrid :columns="2">
              <FormField label="ID konta">
                ID konta
                <Input v-model="editForm.id" type="text" block />
              </FormField>
              <FormField label="Czas wygaśnięcia">
                Czas wygaśnięcia
                <Input v-model="editForm.expires_at" type="text" block />
              </FormField>
            </FieldGrid>

            <FormField label="secure_c_ses">
              <Input v-model="editForm.secure_c_ses" type="text" block root-class="font-mono" />
            </FormField>

            <FieldGrid :columns="2">
              <FormField label="csesidx">
                csesidx
                <Input v-model="editForm.csesidx" type="text" block />
              </FormField>
              <FormField label="config_id">
                config_id
                <Input v-model="editForm.config_id" type="text" block />
              </FormField>
            </FieldGrid>

            <FormField label="host_c_oses">
              <Input v-model="editForm.host_c_oses" type="text" block />
            </FormField>

            <div
              v-if="editError"
              class="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive"
            >
              {{ editError }}
            </div>
          </div>

          <div class="flex items-center justify-end gap-2 border-t border-border/60 px-6 py-4">
            <Button size="sm" variant="outline" @click="closeEdit">Anuluj</Button>
            <Button size="sm" variant="primary" :disabled="isOperating" @click="saveEdit">Zapisz</Button>
          </div>
      </div>
    </ModalShell>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import {
  Button,
  Checkbox,
  EmptyState,
  FieldGrid,
  FilterSelect,
  FormField,
  Input,
  ModalShell,
  SelectMenu,
  ToolbarShell,
} from 'nanocat-ui'
import AccountBulkBar from '@/components/ai/AccountBulkBar.vue'
import QuotaBadge from '@/components/QuotaBadge.vue'
import ModalSectionHeader from '@/components/ui/ModalSectionHeader.vue'
import TriStateCheckbox from '@/components/ui/TriStateCheckbox.vue'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useToast } from '@/composables/useToast'
import { useAccountsStore } from '@/stores/accounts'
import { useAccountConfigEditor } from './accounts/useAccountConfigEditor'
import { useAccountImportExport } from './accounts/useAccountImportExport'
import { useAccountsPage } from './accounts/useAccountsPage'
import { createAccountOperations } from './accounts/accountOperations'
import {
  accountBatchMenuItems as batchMenuItems,
  displayRemaining,
  getAccountRowClass as rowClass,
  getAccountStatusClass as statusClass,
  getAccountStatusLabel as statusLabel,
  getRemainingClass as remainingClass,
  getTrialBadgeClass as trialBadgeClass,
  shouldShowDisableAccount as shouldShowDisable,
  shouldShowEnableAccount as shouldShowEnable,
} from './accounts/accountPresentation'

const accountsStore = useAccountsStore()
const { isLoading, isOperating, batchProgress } = storeToRefs(accountsStore)
const toast = useToast()
const confirmDialog = useConfirmDialog()

const {
  searchQuery,
  statusFilter,
  statusOptions,
  selectedIds,
  viewMode,
  currentPage,
  pageSize,
  pageSizeOptions,
  selectedCount,
  filteredAccounts,
  paginatedAccounts,
  totalPages,
  allSelected,
  isSelectingAll,
  selectionHint,
  selectionState,
  refreshAccounts,
  toggleSelect,
  toggleSelectAll,
  clearSelection,
} = useAccountsPage(accountsStore)

const {
  isImportOpen,
  importText,
  importError,
  importFormatTips,
  isImporting,
  importFileInput,
  importFileName,
  importTextareaPlaceholder,
  isExportOpen,
  exportScope,
  exportFormat,
  exportScopeOptions,
  exportFormatOptions,
  openImportModal,
  closeImportModal,
  triggerImportFile,
  handleImportFile,
  handleImportSubmit,
  openExportModal,
  closeExportModal,
  runExport,
} = useAccountImportExport(accountsStore, toast, selectedIds, selectedCount)
const {
  isConfigOpen,
  configError,
  configJson,
  configMasked,
  isEditOpen,
  editError,
  editForm,
  openEdit,
  closeEdit,
  saveEdit,
  openConfigPanel,
  closeConfigPanel,
  toggleConfigMask,
  saveConfigPanel,
} = useAccountConfigEditor(accountsStore, toast, selectedIds)
const batchProgressLabel = computed(() => (
  batchProgress.value
    ? `Przetwarzanie ${batchProgress.value.current}/${batchProgress.value.total}`
    : ''
))

const {
  handleBulkEnable,
  handleBulkDisable,
  handleBulkDelete,
  handleBatchAction,
  handleEnable,
  handleDisable,
  handleDelete,
} = createAccountOperations(accountsStore, toast, confirmDialog, selectedIds)

onMounted(async () => {
  await refreshAccounts()
})
</script>
