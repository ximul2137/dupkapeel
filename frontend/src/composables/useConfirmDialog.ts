import { ref } from 'vue'

type ConfirmOptions = {
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
}

const open = ref(false)
const title = ref('Potwierdź operację')
const message = ref('')
const confirmText = ref('Potwierdź')
const cancelText = ref('Anuluj')
let resolver: ((value: boolean) => void) | null = null

export function useConfirmDialog() {
  const ask = (options: ConfirmOptions) =>
    new Promise<boolean>((resolve) => {
      title.value = options.title || 'Potwierdź operację'
      message.value = options.message
      confirmText.value = options.confirmText || 'Potwierdź'
      cancelText.value = options.cancelText || 'Anuluj'
      open.value = true
      resolver = resolve
    })

  const confirm = () => {
    open.value = false
    resolver?.(true)
    resolver = null
  }

  const cancel = () => {
    open.value = false
    resolver?.(false)
    resolver = null
  }

  return {
    open,
    title,
    message,
    confirmText,
    cancelText,
    ask,
    confirm,
    cancel,
  }
}
