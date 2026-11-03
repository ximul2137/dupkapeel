<template>
  <div class="flex items-center justify-between border-b border-border/60 px-6 py-4">
    <div>
      <slot>
        <p v-if="title" class="text-sm font-medium text-foreground">{{ title }}</p>
        <p v-if="description" class="mt-1 text-xs text-muted-foreground">
          {{ description }}
        </p>
      </slot>
    </div>
    <div v-if="$slots.actions" class="flex items-center gap-2">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
  description?: string
}>()
</script>
