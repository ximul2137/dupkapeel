<template>
  <div class="ui-panel">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="ui-section-title">Logi administracyjne</p>
      <p class="text-xs text-muted-foreground">Bieżące: {{ parsedLogs.length }}</p>
    </div>

    <div class="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <div class="ui-card-sm text-center">
        <div class="text-[11px] text-muted-foreground">Wszystkie</div>
        <div class="mt-1 text-lg font-semibold text-foreground">{{ stats?.memory.total ?? 0 }}</div>
      </div>
      <div class="ui-card-sm text-center">
        <div class="text-[11px] text-muted-foreground">Rozmowy</div>
        <div class="mt-1 text-lg font-semibold text-foreground">{{ stats?.chat_count ?? 0 }}</div>
      </div>
      <div class="ui-card-sm text-center">
        <div class="text-[11px] text-muted-foreground">INFO</div>
        <div class="mt-1 text-lg font-semibold text-foreground">{{ stats?.memory.by_level.INFO ?? 0 }}</div>
      </div>
      <div class="ui-card-sm text-center">
        <div class="text-[11px] text-muted-foreground">WARNING</div>
        <div class="mt-1 text-lg font-semibold text-foreground">{{ stats?.memory.by_level.WARNING ?? 0 }}</div>
      </div>
      <div class="ui-card-sm text-center">
        <div class="text-[11px] text-muted-foreground">ERROR</div>
        <div class="mt-1 text-lg font-semibold" :class="(stats?.memory.by_level.ERROR ?? 0) > 0 ? 'text-rose-600' : 'text-foreground'">
          {{ stats?.memory.by_level.ERROR ?? 0 }}
        </div>
      </div>
      <div class="ui-card-sm text-center">
        <div class="text-[11px] text-muted-foreground">Limit bufora</div>
        <div class="mt-1 text-lg font-semibold text-foreground">{{ stats?.memory.capacity ?? 0 }}</div>
      </div>
    </div>

    <div class="mt-4 w-full">
      <div class="flex w-full flex-wrap items-center gap-2">
        <div class="w-[150px] shrink-0">
          <SelectMenu v-model="filters.level" :options="levelOptions" />
        </div>
        <Input
          :model-value="filters.search"
          type="text"
          placeholder="Szukaj w logach..."
          block
          root-class="min-w-[11rem] flex-1 md:min-w-[260px]"
          @update:model-value="filters.search = $event.trim()"
        />
        <Input
          :model-value="filters.limit"
          type="number"
          root-class="w-[96px] shrink-0"
          @update:model-value="filters.limit = $event === '' ? 300 : Number($event)"
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          root-class="shrink-0"
          :disabled="isFetching"
          @click="fetchLogs"
        >
          Odśwież
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          root-class="shrink-0"
          @click="exportLogs"
        >
          Eksportuj
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          root-class="shrink-0"
          @click="confirmOpen = true"
        >
          Wyczyść
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          root-class="shrink-0"
          @click="toggleView"
        >
          {{ rawView ? 'Widok strukturalny' : 'Widok surowy' }}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          root-class="shrink-0"
          @click="toggleDetailMode"
        >
          {{ detailMode === 'summary' ? 'Podsumowanie' : 'Szczegóły' }}
        </Button>
        <Button
          type="button"
          size="sm"
          :variant="autoRefreshEnabled ? 'primary' : 'outline'"
          root-class="shrink-0"
          @click="toggleAutoRefresh"
        >
          {{ autoRefreshEnabled ? 'Auto-odświeżanie 8s' : 'Auto-odświeżanie wył.' }}
        </Button>
      </div>
    </div>

    <div
      v-if="rawView"
      ref="rawLogContainer"
      class="scrollbar-slim mt-4 max-h-[60vh] overflow-x-auto overflow-y-auto rounded-2xl border border-border bg-muted/30 px-4 py-3 text-[11px] text-muted-foreground"
    >
      <pre class="whitespace-pre font-mono leading-relaxed">{{ rawLogView.text }}</pre>
      <p v-if="rawLogView.limited" class="mt-2 text-[10px]">Wyświetlono ostatnie {{ rawLogView.showing }} z {{ rawLogView.total }}</p>
    </div>

    <div
      v-else
      ref="structuredLogContainer"
      class="scrollbar-slim ui-card-sm mt-4 max-h-[60vh] space-y-3 overflow-y-auto"
    >
      <div v-if="structuredView.ungrouped.length === 0 && structuredView.groups.length === 0" class="text-xs text-muted-foreground">
        Brak logów
      </div>

      <DynamicScroller
        v-if="shouldVirtualizeUngrouped"
        :items="structuredView.ungrouped"
        key-field="rowId"
        :min-item-size="54"
        class="max-h-[26vh] overflow-y-auto pr-1"
      >
        <template #default="{ item: log, index }">
          <DynamicScrollerItem :item="log" :active="true" :size-dependencies="[log.text, detailMode]">
            <div :class="index > 0 ? 'pt-2' : ''">
              <LogEntryRow
                :time="log.time"
                :text="log.text"
                :badge-text="log.level"
                :badge-class="levelBadgeClass(log.level)"
                :tags="buildLogTags(log)"
                :account-text="log.accountId"
                :account-style="buildAccountStyle(log.accountId)"
              />
            </div>
          </DynamicScrollerItem>
        </template>
      </DynamicScroller>
      <template v-else>
        <div v-for="(log, index) in structuredView.ungrouped" :key="`u-${log.rowId}-${index}`">
          <LogEntryRow
            :time="log.time"
            :text="log.text"
            :badge-text="log.level"
            :badge-class="levelBadgeClass(log.level)"
            :tags="buildLogTags(log)"
            :account-text="log.accountId"
            :account-style="buildAccountStyle(log.accountId)"
          />
        </div>
      </template>

      <RequestLogGroup
        v-for="group in structuredView.groups"
        :key="group.id"
        :status-label="statusLabel(group.status)"
        :status-badge-class="statusBadgeClass(group.status)"
        :request-id="group.id"
        :collapsed="isCollapsed(group.id)"
        :count-text="`${group.logs.length} wpisów`"
        :account-text="group.accountId"
        :account-style="buildAccountStyle(group.accountId)"
        :meta-texts="groupMetaTexts(group)"
        :hint-text="groupHintText(group)"
        @toggle="toggleGroup(group.id)"
      >
        <RequestLayerSection
          v-for="section in getGroupLayerSections(group)"
          :key="`${group.id}-${section.key}`"
          :label="section.label"
          :badge-class="section.badgeClass"
          :count="section.logs.length"
        >
          <DynamicScroller
            v-if="shouldVirtualizeLayer(section.logs)"
            :items="section.logs"
            key-field="rowId"
            :min-item-size="54"
            class="max-h-[44vh] overflow-y-auto pr-1"
          >
            <template #default="{ item: log, index }">
              <DynamicScrollerItem :item="log" :active="true" :size-dependencies="[log.text, detailMode]">
                <div :class="index > 0 ? 'pt-2' : ''">
                  <LogEntryRow
                    :time="log.time"
                    :text="log.text"
                    :badge-text="log.level"
                    :badge-class="levelBadgeClass(log.level)"
                    :tags="buildLogTags(log)"
                    :account-text="log.accountId"
                    :account-style="buildAccountStyle(log.accountId)"
                  />
                </div>
              </DynamicScrollerItem>
            </template>
          </DynamicScroller>
          <div v-else class="space-y-2">
            <LogEntryRow
              v-for="(log, logIndex) in section.logs"
              :key="`${group.id}-${section.key}-${log.rowId}-${logIndex}`"
              :time="log.time"
              :text="log.text"
              :badge-text="log.level"
              :badge-class="levelBadgeClass(log.level)"
              :tags="buildLogTags(log)"
              :account-text="log.accountId"
              :account-style="buildAccountStyle(log.accountId)"
            />
          </div>
        </RequestLayerSection>
      </RequestLogGroup>
    </div>
  </div>

  <ConfirmDialog
    :open="confirmOpen"
    title="Potwierdź operację"
    message="Czy na pewno wyczyścić wszystkie logi?"
    confirm-text="Potwierdź"
    cancel-text="Anuluj"
    @confirm="clearLogs"
    @cancel="confirmOpen = false"
  />
</template>

<script setup lang="ts">
import { Button, ConfirmDialog, Input, SelectMenu } from 'nanocat-ui'
import { DynamicScroller, DynamicScrollerItem } from 'vue-virtual-scroller'
import LogEntryRow from '@/components/ai/LogEntryRow.vue'
import RequestLayerSection from '@/components/ai/RequestLayerSection.vue'
import RequestLogGroup from '@/components/ai/RequestLogGroup.vue'
import { useLogsPage } from './logsPage/useLogsPage'

const {
  parsedLogs,
  stats,
  filters,
  levelOptions,
  isFetching,
  fetchLogs,
  exportLogs,
  confirmOpen,
  rawView,
  toggleView,
  detailMode,
  toggleDetailMode,
  autoRefreshEnabled,
  toggleAutoRefresh,
  rawLogContainer,
  structuredLogContainer,
  rawLogView,
  structuredView,
  shouldVirtualizeUngrouped,
  levelBadgeClass,
  buildAccountStyle,
  buildLogTags,
  isGroupLimited,
  groupLogLimit,
  groupMetaTexts,
  groupHintText,
  isCollapsed,
  toggleGroup,
  statusBadgeClass,
  statusLabel,
  getGroupLayerSections,
  shouldVirtualizeLayer,
  clearLogs,
} = useLogsPage()
</script>
