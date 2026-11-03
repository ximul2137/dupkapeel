import { computed, ref } from 'vue'
import type { useToast } from '@/composables/useToast'
import type { useAccountsStore } from '@/stores/accounts'
import { loadAccountConfigList } from './accountConfig'
import {
  buildAccountExportPayload,
  looksLikeJsonImport,
  mergeJsonImportItems,
  mergeTextImportItems,
  normalizeJsonImportList,
  parseImportLines,
} from './accountImportExport'

type AccountStore = ReturnType<typeof useAccountsStore>
type ToastApi = ReturnType<typeof useToast>
type SelectionRef = { value: Set<string> }
type SelectedCountRef = { value: number }

const exportFormatOptions = [
  { label: 'JSON', value: 'json' },
  { label: 'TXT', value: 'txt' },
] as const

const importFormatTips = [
  'Tablica JSON lub obiekt JSON z polem accounts',
  'duckmail / moemail: provider----email----hasło',
  'freemail: freemail----email----base_url----jwt_token----verify_ssl----domain',
  'gptmail: gptmail----email',
  'cfmail: cfmail----email----hasło',
  'Microsoft / OAuth: email----hasło----client_id----refresh_token',
] as const

const importTextareaPlaceholder = [
  'Obsługuje tablicę JSON, obiekt JSON (z polem accounts) oraz import wiersz po wierszu.',
  '',
  'Przykłady:',
  'duckmail----email----hasło',
  'moemail----email----hasło',
  'freemail----email----base_url----jwt_token----true----domain',
  'gptmail----email',
  'cfmail----email----hasło',
  'email----hasło----client_id----refresh_token',
  '',
  'Wskazówka: możesz też użyć skryptu import_cookies.py z folderu projektu.',
].join('\n')

const downloadText = (content: string, filename: string, mime: string) => {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

export function useAccountImportExport(
  accountsStore: AccountStore,
  toast: ToastApi,
  selectedIds: SelectionRef,
  selectedCount: SelectedCountRef,
) {
  const isImportOpen = ref(false)
  const importText = ref('')
  const importError = ref('')
  const isImporting = ref(false)
  const importFileInput = ref<HTMLInputElement | null>(null)
  const importFileName = ref('')

  const isExportOpen = ref(false)
  const exportScope = ref<'all' | 'selected'>('all')
  const exportFormat = ref<'json' | 'txt'>('json')

  const exportScopeOptions = computed(() => [
    { label: 'Wszystkie konta', value: 'all' },
    { label: `Zaznaczone (${selectedCount.value})`, value: 'selected' },
  ])

  const openImportModal = () => {
    isImportOpen.value = true
    importText.value = ''
    importError.value = ''
    importFileName.value = ''
  }

  const closeImportModal = () => {
    isImportOpen.value = false
    importText.value = ''
    importError.value = ''
    importFileName.value = ''
  }

  const triggerImportFile = () => {
    importFileInput.value?.click()
  }

  const handleImportFile = async (event: Event) => {
    const target = event.target as HTMLInputElement | null
    const file = target?.files?.[0]
    if (!file) return

    try {
      importText.value = await file.text()
      importFileName.value = file.name
      importError.value = ''
    } catch (error: any) {
      importError.value = error.message || 'Błąd odczytu pliku'
    } finally {
      if (target) {
        target.value = ''
      }
    }
  }

  const applyImportedAccounts = async (
    importedIds: string[],
    successMessage: string,
    next: Awaited<ReturnType<typeof loadAccountConfigList>>,
  ) => {
    await accountsStore.updateConfig(next)
    selectedIds.value = new Set(importedIds)
    toast.success(successMessage)
  }

  const handleImportSubmit = async () => {
    importError.value = ''
    const raw = importText.value.trim()
    if (!raw) {
      importError.value = 'Wprowadź dane do importu'
      return
    }

    isImporting.value = true
    try {
      const existing = await loadAccountConfigList()

      if (looksLikeJsonImport(importFileName.value, raw)) {
        const items = normalizeJsonImportList(raw)
        const { next, importedIds } = mergeJsonImportItems(existing, items)
        await applyImportedAccounts(importedIds, `Zaimportowano ${importedIds.length} kont`, next)
      } else {
        const { items, errors } = parseImportLines(raw)
        if (!items.length) {
          throw new Error(errors.length ? errors.join(', ') : 'Nie rozpoznano poprawnych kont')
        }
        if (errors.length) {
          throw new Error(errors.slice(0, 3).join(', '))
        }
        const { next, importedIds } = mergeTextImportItems(existing, items)
        await applyImportedAccounts(importedIds, `Pomyślnie zaimportowano ${importedIds.length} kont`, next)
      }

      closeImportModal()
    } catch (error: any) {
      importError.value = error.message || 'Błąd importu'
      toast.error(error.message || 'Błąd importu')
    } finally {
      isImporting.value = false
    }
  }

  const openExportModal = () => {
    exportScope.value = selectedCount.value > 0 ? 'selected' : 'all'
    exportFormat.value = 'json'
    isExportOpen.value = true
  }

  const closeExportModal = () => {
    isExportOpen.value = false
  }

  const exportConfig = async (format: 'json' | 'txt', scope: 'all' | 'selected') => {
    let list = await loadAccountConfigList()
    if (scope === 'selected') {
      if (!selectedIds.value.size) {
        throw new Error('Nie zaznaczono żadnych kont')
      }
      list = list.filter((item) => selectedIds.value.has(item.id))
    }

    const payload = buildAccountExportPayload(list, format)
    downloadText(payload.content, payload.filename, payload.mime)
    toast.success(payload.successMessage)
  }

  const runExport = async () => {
    try {
      await exportConfig(exportFormat.value, exportScope.value)
      closeExportModal()
    } catch (error: any) {
      toast.error(error.message || 'Błąd eksportu')
    }
  }

  return {
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
  }
}
