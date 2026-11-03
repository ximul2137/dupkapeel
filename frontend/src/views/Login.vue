<template>
  <div class="min-h-screen px-4">
    <div class="flex min-h-screen items-center justify-center">
      <div class="w-full max-w-md rounded-[2.5rem] border border-border bg-card p-10 shadow-2xl shadow-black/10">
        <div class="text-center">
          <h1 class="text-3xl font-semibold text-foreground">geminienterprise-grupkapeel</h1>
          <p class="mt-2 text-sm text-muted-foreground">Logowanie administratora</p>
        </div>

        <form class="mt-8 space-y-6" @submit.prevent="handleLogin">
          <div v-if="defaultAdminKeyActive" class="rounded-2xl bg-amber-500/10 px-4 py-3 text-sm text-amber-700">
            Nie ustawiono <code>ADMIN_KEY</code>, domyślne hasło: 123456
          </div>

          <div class="space-y-2">
            <label for="password" class="ui-field-label text-sm font-medium text-foreground">
              Hasło administratora
            </label>
            <Input
              id="password"
              v-model="password"
              type="password"
              size="md"
              block
              placeholder="Wpisz hasło administratora"
              :disabled="isLoading"
            />
          </div>

          <div v-if="errorMessage" class="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {{ errorMessage }}
          </div>

          <Button
            type="submit"
            size="md"
            variant="primary"
            block
            :disabled="isLoading || !password"
          >
            {{ isLoading ? 'Logowanie...' : 'Zaloguj się' }}
          </Button>
        </form>

        <div class="mt-8 flex items-center justify-center gap-4 text-xs text-muted-foreground">
          <span>geminienterprise-grupkapeel</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button, Input } from 'nanocat-ui'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { versionApi } from '@/api/version'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const password = ref('')
const errorMessage = ref('')
const isLoading = ref(false)
const defaultAdminKeyActive = ref(false)

async function loadVersionInfo() {
  try {
    const versionInfo = await versionApi.current()
    defaultAdminKeyActive.value = Boolean(versionInfo.default_admin_key_active)
  } catch {
    defaultAdminKeyActive.value = false
  }
}

async function handleLogin() {
  if (!password.value) return

  errorMessage.value = ''
  isLoading.value = true

  try {
    await authStore.login(password.value)
    router.push({ name: 'dashboard' })
  } catch (error: any) {
    errorMessage.value = error.message || 'Logowanie nie powiodło się, sprawdź hasło.'
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  void loadVersionInfo()
})
</script>
