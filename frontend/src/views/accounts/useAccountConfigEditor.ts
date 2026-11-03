import { ref } from 'vue'
import type { useToast } from '@/composables/useToast'
import type { useAccountsStore } from '@/stores/accounts'
import type { AccountConfigItem } from '@/types/accounts'
import {
  applyAccountEditForm,
  createAccountEditForm,
  createEmptyAccountEditForm,
  loadAccountConfigList,
  maskConfig,
  parseConfigEditorJson,
  type AccountEditForm,
} from './accountConfig'

type AccountStore = ReturnType<typeof useAccountsStore>
type ToastApi = ReturnType<typeof useToast>
type SelectionRef = { value: Set<string> }

export function useAccountConfigEditor(
  accountsStore: AccountStore,
  toast: ToastApi,
  selectedIds: SelectionRef,
) {
  const isConfigOpen = ref(false)
  const configError = ref('')
  const configJson = ref('')
  const configMasked = ref(false)
  const configData = ref<AccountConfigItem[]>([])

  const isEditOpen = ref(false)
  const editError = ref('')
  const editIndex = ref<number | null>(null)
  const configAccounts = ref<AccountConfigItem[]>([])
  const editForm = ref<AccountEditForm>(createEmptyAccountEditForm())

  const applyEditTarget = (list: AccountConfigItem[], accountId: string) => {
    const targetIndex = list.findIndex((account) => account.id === accountId)
    if (targetIndex === -1) {
      editError.value = 'Nie znaleziono konfiguracji konta.'
      return
    }

    const target = list[targetIndex]
    editForm.value = createAccountEditForm(target)
    configAccounts.value = list
    editIndex.value = targetIndex
    isEditOpen.value = true
  }

  const openEdit = async (accountId: string) => {
    editError.value = ''
    try {
      const list = await loadAccountConfigList()
      applyEditTarget(list, accountId)
    } catch (error: any) {
      editError.value = error.message || 'Błąd ładowania konfiguracji kont'
    }
  }

  const closeEdit = () => {
    isEditOpen.value = false
    editError.value = ''
    editIndex.value = null
  }

  const saveEdit = async () => {
    if (editIndex.value === null) return

    const next = applyAccountEditForm(configAccounts.value, editIndex.value, editForm.value)

    try {
      await accountsStore.updateConfig(next)
      toast.success('Zapisano zmiany konta')
      selectedIds.value = new Set([editForm.value.id.trim()])
      closeEdit()
    } catch (error: any) {
      editError.value = error.message || 'Błąd zapisu'
      toast.error(error.message || 'Błąd zapisu')
    }
  }

  const openConfigPanel = async () => {
    configError.value = ''
    try {
      configData.value = await loadAccountConfigList()
      configJson.value = JSON.stringify(maskConfig(configData.value), null, 2)
      configMasked.value = true
      isConfigOpen.value = true
    } catch (error: any) {
      configError.value = error.message || 'Błąd ładowania konfiguracji kont'
    }
  }

  const closeConfigPanel = () => {
    isConfigOpen.value = false
    configError.value = ''
    configMasked.value = false
  }

  const toggleConfigMask = () => {
    configError.value = ''
    if (!configMasked.value) {
      try {
        configData.value = parseConfigEditorJson(configJson.value)
      } catch (error: any) {
        configError.value = error.message || 'Błąd formatu JSON'
        return
      }
      configJson.value = JSON.stringify(maskConfig(configData.value), null, 2)
      configMasked.value = true
      return
    }

    configJson.value = JSON.stringify(configData.value, null, 2)
    configMasked.value = false
  }

  const saveConfigPanel = async () => {
    configError.value = ''
    if (configMasked.value) {
      configError.value = 'Przełącz na jawny tekst przed zapisaniem konfiguracji.'
      return
    }

    try {
      const parsed = parseConfigEditorJson(configJson.value)
      await accountsStore.updateConfig(parsed)
      toast.success('Zapisano konfigurację')
      closeConfigPanel()
    } catch (error: any) {
      configError.value = error.message || 'Błąd zapisu'
      toast.error(error.message || 'Błąd zapisu')
    }
  }

  return {
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
  }
}
