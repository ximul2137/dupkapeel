<template>
  <div class="flex items-center justify-between gap-2">
    <p class="ui-section-kicker">{{ title }}</p>
    <div v-if="helpText || $slots.trailing" class="flex items-center gap-2">
      <HelpTip v-if="helpText" :text="helpText" />
      <slot name="trailing" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { HelpTip } from 'nanocat-ui'

defineProps<{
  title: string
  helpText?: string
}>()
</script>
