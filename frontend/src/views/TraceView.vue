<template>
  <PageHeader title="Trace">
    <template #subtitle>
      <span class="mono" style="font-size: 13px; color: var(--accent-2)">{{ traceId }}</span>
    </template>
    <template #actions>
      <button class="sm ghost" @click="goBack"><AppIcon name="chevron-left" :size="14" /> All traces</button>
      <button class="sm" @click="copyId"><AppIcon :name="copied ? 'check' : 'copy'" :size="14" /> {{ copied ? 'Copied' : 'Copy ID' }}</button>
      <button class="sm subtle" @click="openInExplorer"><AppIcon name="logs" :size="14" /> Explorer</button>
    </template>
  </PageHeader>

  <div v-if="error" class="alert"><AppIcon name="alert-circle" :size="16" />{{ error }}</div>

  <div v-if="loading" class="stats">
    <div v-for="n in 4" :key="n" class="stat"><div class="skeleton" style="height: 52px"></div></div>
  </div>
  <template v-else-if="detail">
    <div class="stats">
      <StatCard label="Spans" :value="detail.count" tone="violet" icon="activity" class="rise" />
      <StatCard label="Services" :value="detail.services.length" tone="info" icon="server" class="rise rise-1" />
      <div class="stat tone-ok rise rise-2">
        <div class="stat-top"><span class="stat-icon"><AppIcon name="timer" :size="16" /></span><span class="label">Duration</span></div>
        <div class="value">{{ formatDuration(detail.duration_seconds) }}</div>
        <div class="sub-line">{{ formatDateTime(detail.first_seen) }}</div>
      </div>
      <div class="stat rise rise-3">
        <div class="stat-top"><span class="stat-icon"><AppIcon name="clock" :size="16" /></span><span class="label">Time range</span></div>
        <div class="value" style="font-size: 15px; line-height: 1.5">{{ formatDateTime(detail.first_seen) }}<br />{{ formatDateTime(detail.last_seen) }}</div>
      </div>
    </div>

    <div class="panel rise rise-2">
      <div class="toolbar">
        <span style="display: inline-flex; gap: 6px; flex-wrap: wrap; align-items: center">
          <span class="chip" v-for="(svc, i) in detail.services" :key="svc">
            <span class="svc-dot" :style="{ background: serviceColor(i) }"></span>{{ svc }}
          </span>
          <span v-if="!detail.services.length" class="faint" style="font-size: 12.5px">no service attribution</span>
        </span>
        <span class="spacer"></span>
        <SeverityBadge v-for="sev in detail.severities" :key="sev" :severity="sev" />
      </div>

      <div v-if="lanes.length">
        <div class="trace-axis" aria-hidden="true">
          <span
            v-for="tick in axisTicks"
            :key="tick.label"
            :style="{
              left: `${tick.at}%`,
              transform: tick.edge === 'left' ? 'none' : tick.edge === 'right' ? 'translateX(-100%)' : 'translateX(-50%)',
            }"
          >{{ tick.label }}</span>
        </div>
        <button v-for="lane in lanes" :key="lane.entry.id" class="tlane" @click="selected = lane.entry">
          <span class="tlane-meta">
            <span class="tlane-svc">
              <span class="svc-dot" :style="{ background: lane.color }"></span>
              {{ lane.entry.service ?? 'unknown' }}
            </span>
            <span class="tlane-time">+{{ formatOffset(lane.offsetMs) }} · {{ formatClock(lane.entry.timestamp) }}</span>
          </span>
          <span class="tlane-track">
            <span
              class="tlane-bar"
              :style="{
                left: `${lane.leftPct}%`,
                width: `${lane.widthPct}%`,
                background: lane.bg,
                borderColor: lane.color,
                color: lane.color,
              }"
              :title="lane.entry.message"
            >
              <SeverityBadge v-if="isSevere(lane.entry.severity)" :severity="lane.entry.severity" />
              <span style="overflow: hidden; text-overflow: ellipsis; color: var(--text-1)">{{ truncate(firstLine(lane.entry.message), 120) }}</span>
            </span>
          </span>
        </button>
        <p v-if="detail.count > detail.entries.length" class="dim" style="font-size: 12.5px; margin: 12px 4px 0">
          Showing {{ detail.entries.length }} of {{ formatNumber(detail.count) }} spans (capped).
        </p>
      </div>
      <EmptyState v-else title="No spans" icon="traces" hint="This trace has no stored entries." />
    </div>
  </template>

  <LogDetails :entry="selected" @close="selected = null" />
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, type LogEntry, type TraceDetail } from '../api/client'
import { formatDateTime, formatNumber, truncate } from '../utils/format'
import { isErrorLike } from '../utils/severity'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import LogDetails from '../components/LogDetails.vue'
import PageHeader from '../components/PageHeader.vue'
import SeverityBadge from '../components/SeverityBadge.vue'
import StatCard from '../components/StatCard.vue'

const route = useRoute()
const router = useRouter()
const traceId = computed(() => String(route.params.id ?? ''))
const detail = ref<TraceDetail | null>(null)
const loading = ref(true)
const error = ref('')
const selected = ref<LogEntry | null>(null)
const copied = ref(false)

const SERVICE_PALETTE = ['#8b5cf6', '#22d3ee', '#34d399', '#fbbf24', '#fb7185', '#60a5fa', '#fb923c', '#a3e635']

function serviceColor(index: number): string {
  return SERVICE_PALETTE[index % SERVICE_PALETTE.length]
}

function serviceIndex(name: string | null): number {
  if (!detail.value) return 0
  const idx = detail.value.services.indexOf(name ?? '')
  if (idx >= 0) return idx
  let hash = 0
  const s = name ?? '?'
  for (let i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) >>> 0
  return hash % SERVICE_PALETTE.length
}

function toMs(iso: string | null): number | null {
  if (!iso) return null
  const t = new Date(iso).getTime()
  return Number.isNaN(t) ? null : t
}

const timeBounds = computed(() => {
  const stamps = (detail.value?.entries ?? []).map((e) => toMs(e.timestamp)).filter((t): t is number => t !== null)
  if (!stamps.length) return { min: 0, span: 1 }
  const min = Math.min(...stamps)
  const max = Math.max(...stamps)
  return { min, span: Math.max(1, max - min) }
})

interface Lane {
  entry: LogEntry
  offsetMs: number
  leftPct: number
  widthPct: number
  color: string
  bg: string
}

const lanes = computed<Lane[]>(() => {
  if (!detail.value) return []
  const { min, span } = timeBounds.value
  return detail.value.entries.map((entry) => {
    const t = toMs(entry.timestamp)
    const offset = Math.max(0, (t ?? min) - min)
    const left = Math.min(92, (offset / span) * 100)
    const color = serviceColor(serviceIndex(entry.service))
    return {
      entry,
      offsetMs: offset,
      leftPct: left,
      widthPct: Math.max(6, Math.min(100 - left, 42)),
      color,
      bg: `${color}29`,
    }
  })
})

const axisTicks = computed(() => {
  const { span } = timeBounds.value
  return [0, 0.25, 0.5, 0.75, 1].map((at) => ({
    at: at * 100,
    label: `+${formatOffset(span * at)}`,
    edge: at === 0 ? 'left' : at === 1 ? 'right' : 'middle',
  }))
})

function isSevere(sev: string): boolean {
  return isErrorLike(sev)
}

function firstLine(message: string): string {
  const idx = message.indexOf('\n')
  return idx === -1 ? message : `${message.slice(0, idx)}…`
}

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`
  if (seconds < 60) return `${seconds.toFixed(1)} s`
  return `${(seconds / 60).toFixed(1)} min`
}

function formatOffset(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

function formatClock(iso: string | null): string {
  if (!iso) return 'no time'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) +
    `.${String(d.getMilliseconds()).padStart(3, '0')}`
}

function goBack() {
  router.push('/traces')
}

function openInExplorer() {
  // /traces/{id} matches trace_id OR request_id: filter by whichever this
  // id actually is, otherwise a request-id "trace" opens an empty Explorer.
  const id = traceId.value
  const isTrace = detail.value?.entries.some((e) => e.trace_id === id) ?? true
  router.push({ path: '/logs', query: isTrace ? { trace_id: id } : { request_id: id } })
}

async function copyId() {
  try {
    await navigator.clipboard.writeText(traceId.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    copied.value = false
  }
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

<style scoped>
.svc-dot {
  width: 8px;
  height: 8px;
  border-radius: 3px;
  display: inline-block;
  flex-shrink: 0;
}
.chip .svc-dot {
  width: 7px;
  height: 7px;
}
.tlane-bar .sev {
  flex-shrink: 0;
  margin-right: 8px;
  font-size: 9.5px;
  padding: 1px 7px 1px 6px;
}
</style>
