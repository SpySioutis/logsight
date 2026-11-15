<template>
  <div class="page-head">
    <h1>Trace</h1>
    <span class="mono sub">{{ traceId }}</span>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>

  <div v-if="loading" class="panel dim">Loading…</div>
  <template v-else-if="detail">
    <div class="stats">
      <StatCard label="Entries" :value="detail.count" />
      <StatCard label="Services" :value="detail.services.length" />
      <div class="stat">
        <div class="label">Duration</div>
        <div class="value">{{ formatDuration(detail.duration_seconds) }}</div>
      </div>
      <div class="stat">
        <div class="label">First seen</div>
        <div class="value" style="font-size: 16px">{{ formatDateTime(detail.first_seen) }}</div>
      </div>
      <div class="stat">
        <div class="label">Last seen</div>
        <div class="value" style="font-size: 16px">{{ formatDateTime(detail.last_seen) }}</div>
      </div>
    </div>

    <div class="panel">
      <div class="toolbar">
        <span class="dim">Services: {{ detail.services.join(', ') || '—' }}</span>
        <span class="spacer"></span>
        <span v-for="sev in detail.severities" :key="sev" style="margin-left: 6px">
          <SeverityBadge :severity="sev" />
        </span>
      </div>
      <div v-if="detail.entries.length">
        <LogTable :entries="detail.entries" sort="timestamp" direction="asc" @select="selected = $event" @sort="() => {}" />
        <p v-if="detail.count > detail.entries.length" class="dim">
          Showing {{ detail.entries.length }} of {{ formatNumber(detail.count) }} entries (capped).
        </p>
      </div>
      <EmptyState v-else title="No entries" hint="This trace has no stored entries." />
    </div>
  </template>

  <LogDetails :entry="selected" @close="selected = null" />
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, type LogEntry, type TraceDetail } from '../api/client'
import { formatDateTime, formatNumber } from '../utils/format'
import EmptyState from '../components/EmptyState.vue'
import LogDetails from '../components/LogDetails.vue'
import LogTable from '../components/LogTable.vue'
import SeverityBadge from '../components/SeverityBadge.vue'
import StatCard from '../components/StatCard.vue'

const route = useRoute()
const traceId = computed(() => String(route.params.id ?? ''))
const detail = ref<TraceDetail | null>(null)
const loading = ref(true)
const error = ref('')
const selected = ref<LogEntry | null>(null)

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`
  if (seconds < 60) return `${seconds.toFixed(1)} s`
  return `${(seconds / 60).toFixed(1)} min`
}

async function load() {
  loading.value = true
  error.value = ''
  detail.value = null
  try {
    detail.value = (await api.get(`/traces/${encodeURIComponent(traceId.value)}`)).data
  } catch {
    error.value = `Trace "${traceId.value}" was not found.`
  } finally {
    loading.value = false
  }
}

watch(traceId, load)
onMounted(load)
</script>
