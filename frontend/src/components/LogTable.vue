<template>
  <div class="table-wrap">
    <table class="grid">
      <thead>
        <tr>
          <th style="width: 176px">
            <button class="th-sort" @click="toggleSort('timestamp')">
              Timestamp
              <AppIcon v-if="sort === 'timestamp'" :name="direction === 'asc' ? 'arrow-up' : 'arrow-down'" :size="12" />
            </button>
          </th>
          <th style="width: 118px">Severity</th>
          <th style="width: 150px">
            <button class="th-sort" @click="toggleSort('service')">
              Service
              <AppIcon v-if="sort === 'service'" :name="direction === 'asc' ? 'arrow-up' : 'arrow-down'" :size="12" />
            </button>
          </th>
          <th style="width: 150px">
            <button class="th-sort" @click="toggleSort('source')">
              Source
              <AppIcon v-if="sort === 'source'" :name="direction === 'asc' ? 'arrow-up' : 'arrow-down'" :size="12" />
            </button>
          </th>
          <th>Message</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="entry in entries" :key="entry.id" class="rowlink" @click="$emit('select', entry)">
          <td class="mono nowrap dim" style="font-size: 12px">{{ formatDateTime(entry.timestamp) }}</td>
          <td><SeverityBadge :severity="entry.severity" /></td>
          <td class="ellipsis" :title="entry.service ?? ''">{{ entry.service ?? '—' }}</td>
          <td class="ellipsis dim" :title="entry.source ?? ''">{{ entry.source ?? '—' }}</td>
          <td class="mono ellipsis" :title="entry.message" style="font-size: 12.5px">
            <span v-if="entry.snippet" v-html="safeSnippet(entry.snippet)"></span>
            <template v-else>{{ truncate(firstLine(entry.message), 180) }}</template>
            <RouterLink
              v-if="entry.trace_id"
              :to="`/traces/${encodeURIComponent(entry.trace_id)}`"
              class="trace-chip"
              :title="`Open trace ${entry.trace_id}`"
              @click.stop
            >
              trace:{{ truncate(entry.trace_id, 12) }}
            </RouterLink>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { LogEntry } from '../api/client'
import { formatDateTime, truncate } from '../utils/format'
import { sanitizeSnippet } from '../utils/highlight'
import AppIcon from './AppIcon.vue'
import SeverityBadge from './SeverityBadge.vue'

defineProps<{
  entries: LogEntry[]
  sort: string
  direction: 'asc' | 'desc'
}>()

const emit = defineEmits<{
  (e: 'select', entry: LogEntry): void
  (e: 'sort', field: string): void
}>()

function toggleSort(field: string) {
  emit('sort', field)
}

function safeSnippet(snippet: string): string {
  return sanitizeSnippet(snippet)
}

function firstLine(message: string): string {
  const idx = message.indexOf('\n')
  return idx === -1 ? message : `${message.slice(0, idx)}…`
}
</script>
