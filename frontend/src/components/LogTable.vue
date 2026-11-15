<template>
  <table class="grid">
    <thead>
      <tr>
        <th style="width: 170px">
          <button class="th-sort" @click="toggleSort('timestamp')">
            Timestamp {{ sortArrow('timestamp') }}
          </button>
        </th>
        <th style="width: 96px">Severity</th>
        <th style="width: 150px">
          <button class="th-sort" @click="toggleSort('service')">
            Service {{ sortArrow('service') }}
          </button>
        </th>
        <th style="width: 150px">
          <button class="th-sort" @click="toggleSort('source')">
            Source {{ sortArrow('source') }}
          </button>
        </th>
        <th>Message</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="entry in entries" :key="entry.id" class="rowlink" @click="$emit('select', entry)">
        <td class="mono nowrap dim">{{ formatDateTime(entry.timestamp) }}</td>
        <td><SeverityBadge :severity="entry.severity" /></td>
        <td class="ellipsis" :title="entry.service ?? ''">{{ entry.service ?? '—' }}</td>
        <td class="ellipsis" :title="entry.source ?? ''">{{ entry.source ?? '—' }}</td>
        <td class="mono ellipsis" :title="entry.message">
          <span v-if="entry.snippet" v-html="safeSnippet(entry.snippet)"></span>
          <template v-else>{{ truncate(firstLine(entry.message), 180) }}</template>
          <RouterLink
            v-if="entry.trace_id"
            :to="`/traces/${encodeURIComponent(entry.trace_id)}`"
            class="trace-chip"
            :title="`Trace ${entry.trace_id}`"
            @click.stop
          >
            trace:{{ truncate(entry.trace_id, 12) }}
          </RouterLink>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import type { LogEntry } from '../api/client'
import { formatDateTime, truncate } from '../utils/format'
import { sanitizeSnippet } from '../utils/highlight'
import SeverityBadge from './SeverityBadge.vue'

const props = defineProps<{
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

function sortArrow(field: string): string {
  if (props.sort !== field) return ''
  return props.direction === 'asc' ? '↑' : '↓'
}

function safeSnippet(snippet: string): string {
  return sanitizeSnippet(snippet)
}

function firstLine(message: string): string {
  const idx = message.indexOf('\n')
  return idx === -1 ? message : `${message.slice(0, idx)}…`
}
</script>

<style scoped>
.th-sort {
  background: none;
  border: none;
  padding: 0;
  color: inherit;
  font: inherit;
  cursor: pointer;
  text-transform: inherit;
  letter-spacing: inherit;
}
.trace-chip {
  margin-left: 8px;
  font-size: 11px;
  white-space: nowrap;
}
</style>
