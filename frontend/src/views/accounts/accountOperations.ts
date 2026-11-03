import type { useConfirmDialog } from '@/composables/useConfirmDialog'
import type { useToast } from '@/composables/useToast'
import type { useAccountsStore } from '@/stores/accounts'

type AccountStore = ReturnType<typeof useAccountsStore>
type ToastApi = ReturnType<typeof useToast>
type ConfirmDialogApi = ReturnType<typeof useConfirmDialog>
type SelectionRef = { value: Set<string> }

const formatOpErrors = (errors: string[]) => {
  if (!errors.length) return ''
  const sample = errors[0]
  return `Nieudane: ${errors.length}${sample ? `, przykład: ${sample}` : ''}`
}

const handleOpResult = (
  toast: ToastApi,
  result: { ok: boolean; errors: string[] },
  successMessage: string,
  failMessage: string,
) => {
  if (result.ok) {
    toast.success(successMessage)
    return true
  }

  const detail = formatOpErrors(result.errors)
  toast.error(detail ? `${failMessage}, ${detail}` : failMessage)
  return false
}

const removeSelectedId = (selectedIds: SelectionRef, accountId: string) => {
  if (!selectedIds.value.has(accountId)) return
  const next = new Set(selectedIds.value)
  next.delete(accountId)
  selectedIds.value = next
}

export const createAccountOperations = (
  accountsStore: AccountStore,
  toast: ToastApi,
  confirmDialog: ConfirmDialogApi,
  selectedIds: SelectionRef,
) => {
  const handleBulkEnable = async () => {
    if (!selectedIds.value.size || accountsStore.isOperating) return

    try {
      const result = await accountsStore.bulkEnable(Array.from(selectedIds.value))
      if (handleOpResult(toast, result, 'Włączono zaznaczone konta', 'Błąd zbiorczego włączania')) {
        selectedIds.value = new Set()
      }
    } catch (error: any) {
      toast.error(error.message || 'Błąd zbiorczego włączania')
    }
  }

  const handleBulkDisable = async () => {
    if (!selectedIds.value.size || accountsStore.isOperating) return

    const confirmed = await confirmDialog.ask({
      title: 'Wyłącz zaznaczone',
      message: 'Czy na pewno chcesz wyłączyć zaznaczone konta?',
    })
    if (!confirmed) return

    try {
      const result = await accountsStore.bulkDisable(Array.from(selectedIds.value))
      if (handleOpResult(toast, result, 'Wyłączono zaznaczone konta', 'Błąd zbiorczego wyłączania')) {
        selectedIds.value = new Set()
      }
    } catch (error: any) {
      toast.error(error.message || 'Błąd zbiorczego wyłączania')
    }
  }

  const handleBulkDelete = async () => {
    if (!selectedIds.value.size || accountsStore.isOperating) return

    const confirmed = await confirmDialog.ask({
      title: 'Usuń zaznaczone',
      message: 'Czy na pewno chcesz usunąć zaznaczone konta?',
      confirmText: 'Usuń',
    })
    if (!confirmed) return

    try {
      const result = await accountsStore.bulkDelete(Array.from(selectedIds.value))
      if (handleOpResult(toast, result, 'Usunięto zaznaczone konta', 'Błąd zbiorczego usuwania')) {
        selectedIds.value = new Set()
      }
    } catch (error: any) {
      toast.error(error.message || 'Błąd zbiorczego usuwania')
    }
  }

  const handleBatchAction = async (action: string) => {
    if (action === 'enable') {
      await handleBulkEnable()
      return
    }

    if (action === 'disable') {
      await handleBulkDisable()
      return
    }

    if (action === 'delete') {
      await handleBulkDelete()
    }
  }

  const handleEnable = async (accountId: string) => {
    if (accountsStore.isOperating) return

    try {
      const result = await accountsStore.enableAccount(accountId)
      handleOpResult(toast, result, 'Konto włączone', 'Błąd włączania')
    } catch (error: any) {
      toast.error(error.message || 'Błąd włączania')
    }
  }

  const handleDisable = async (accountId: string) => {
    if (accountsStore.isOperating) return

    const confirmed = await confirmDialog.ask({
      title: 'Wyłącz konto',
      message: 'Czy na pewno chcesz wyłączyć to konto?',
    })
    if (!confirmed) return

    try {
      const result = await accountsStore.disableAccount(accountId)
      handleOpResult(toast, result, 'Konto wyłączone', 'Błąd wyłączania')
    } catch (error: any) {
      toast.error(error.message || 'Błąd wyłączania')
    }
  }

  const handleDelete = async (accountId: string) => {
    if (accountsStore.isOperating) return

    const confirmed = await confirmDialog.ask({
      title: 'Usuń konto',
      message: 'Czy na pewno chcesz usunąć to konto?',
      confirmText: 'Usuń',
    })
    if (!confirmed) return

    try {
      const result = await accountsStore.deleteAccount(accountId)
      if (handleOpResult(toast, result, 'Konto usunięte', 'Błąd usuwania')) {
        removeSelectedId(selectedIds, accountId)
      }
    } catch (error: any) {
      toast.error(error.message || 'Błąd usuwania')
    }
  }

  return {
    handleBulkEnable,
    handleBulkDisable,
    handleBulkDelete,
    handleBatchAction,
    handleEnable,
    handleDisable,
    handleDelete,
  }
}
