<template>
  <PageHeader title="Dashboard">
    <template #subtitle>
      <template v-if="summary && summary.total > 0">
        {{ formatNumber(summary.total) }} stored entries
        <span v-if="dateRange"> · {{ dateRange }}</span>
      </template>
      <template v-else>Overview of your log data</template>
    </template>
    <template #actions>
      <div class="segmented" role="tablist" aria-label="Timeline bucket">
        <button :class="{ active: bucket === 'all' }" title="All stored data, adaptive buckets" @click="setBucket('all')">All</button>
        <button :class="{ active: bucket === 'day' }" title="Last 60 days of data" @click="setBucket('day')">Day</button>
        <button :class="{ active: bucket === 'hour' }" title="Last 60 hours of data" @click="setBucket('hour')">Hour</button>
      </div>
      <button class="ghost sm icon-only" title="Refresh dashboard" @click="refresh">
        <AppIcon name="refresh" :size="15" />
      </button>
    </template>
  </PageHeader>

  <div v-if="error" class="alert"><AppIcon name="alert-circle" :size="16" />{{ error }}</div>

  <div v-if="!loading && summary && summary.total === 0">
    <EmptyState title="No logs yet" icon="sparkles" glow>
      Import a log file to unlock analytics, error grouping and trace correlation.
      <template #cta>
        <RouterLink to="/imports" class="btn primary" style="text-decoration: none">
          <AppIcon name="imports" :size="15" /> Go to Imports
        </RouterLink>
        <a class="btn" href="/api/docs" target="_blank" rel="noopener" style="text-decoration: none">
          <AppIcon name="book" :size="15" /> API docs
        </a>
      </template>
    </EmptyState>
  </div>

  <template v-else>
    <div v-if="loading && !summary" class="stats">
      <div v-for="n in 4" :key="n" class="stat"><div class="skeleton" style="height: 52px"></div></div>
    </div>
    <div class="stats" v-if="summary">
      <StatCard label="Total logs" :value="summary.total" tone="violet" icon="database" :sub="`${formatNumber(summary.imports)} imports`" class="rise" />
      <StatCard label="Errors" :value="summary.errors" tone="danger" icon="errors" :sub="errorShare" class="rise rise-1" />
      <StatCard label="Warnings" :value="summary.warnings" tone="warn" icon="alert-circle" :sub="warningShare" class="rise rise-2" />
      <StatCard label="Active sources" :value="summary.sources" tone="info" icon="server" :sub="`${formatNumber(summary.critical)} critical`" class="rise rise-3" />
    </div>

    <div class="panel rise rise-1">
      <div class="chart-card-head">
        <h2 style="margin: 0"><span class="h2-icon"><AppIcon name="activity" :size="15" /></span> Log volume over time</h2>
        <span class="spacer"></span>
        <span class="chip chip-mono">{{ timelineLabel }}</span>
      </div>
      <div v-if="loadingTimeline"><div class="skeleton" style="height: 190px; border-radius: var(--radius)"></div></div>
      <TimeChart v-else-if="timeline.length" :points="chartPoints" label="Log volume over time" show-errors />
      <EmptyState v-else title="No timeline data" icon="activity" hint="Entries without timestamps are counted but cannot be plotted." />
    </div>

    <div class="grid-auto" style="margin-top: 16px">
      <div class="panel rise rise-2">
        <h2><span class="h2-icon"><AppIcon name="layers" :size="15" /></span> Severity distribution</h2>
        <template v-if="severityDist.length">
          <button
            v-for="row in severityDist"
            :key="row.severity"
            class="dist-row"
            :title="`Show ${row.severity} entries in Explorer`"
            @click="goSeverity(row.severity)"
          >
            <SeverityBadge :severity="row.severity" />
            <span class="bar-track"><span class="bar-fill" :style="{ width: `${barWidth(row.count, maxSeverity)}%`, background: sevColor(row.severity) }"></span></span>
            <span class="dist-val">{{ formatNumber(row.count) }}</span>
          </button>
        </template>
        <EmptyState v-else title="Nothing here yet" icon="layers" />
      </div>

      <div class="panel rise rise-3">
        <h2><span class="h2-icon"><AppIcon name="server" :size="15" /></span> Most active sources</h2>
        <template v-if="topSources.length">
          <button
            v-for="row in topSources"
            :key="row.source"
            class="dist-row"
            :title="`Show entries from ${row.source}`"
            @click="goSource(row.source)"
          >
            <span class="dist-name mono" style="font-size: 12px">{{ row.source }}</span>
            <span class="bar-track"><span class="bar-fill" :style="{ width: `${barWidth(row.count, maxSource)}%`, background: 'var(--accent-gradient)' }"></span></span>
            <span class="dist-val">{{ formatNumber(row.count) }}</span>
          </button>
        </template>
        <EmptyState v-else title="Nothing here yet" icon="server" />
      </div>

      <div class="panel rise rise-4">
        <div class="chart-card-head" style="margin-bottom: 10px">
          <h2 style="margin: 0"><span class="h2-icon"><AppIcon name="errors" :size="15" /></span> Most frequent errors</h2>
          <span class="spacer"></span>
          <RouterLink to="/errors" class="btn sm ghost" style="text-decoration: none">View all <AppIcon name="arrow-right" :size="13" /></RouterLink>
        </div>
        <template v-if="topErrors.length">
          <button
            v-for="(row, i) in topErrors"
            :key="row.fingerprint"
            class="error-row"
            :title="row.sample"
            @click="goErrors"
          >
            <span class="err-rank">{{ i + 1 }}</span>
            <span class="err-msg">{{ truncate(row.sample, 90) }}</span>
            <span class="err-count">{{ formatNumber(row.count) }}×</span>
          </button>
          <p v-if="mutedNote" class="faint" style="font-size: 12px; margin: 10px 4px 0">{{ mutedNote }}</p>
        </template>
        <EmptyState v-else title="No errors recorded" icon="check-circle" hint="Error and fatal entries will appear here." />
      </div>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api, type DashboardSummary, type LogHistogram, type TimelinePoint } from '../api/client'
import { formatMonth, formatNumber, formatShortDate, formatShortDateTime, truncate } from '../utils/format'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import PageHeader from '../components/PageHeader.vue'
import SeverityBadge from '../components/SeverityBadge.vue'
import StatCard from '../components/StatCard.vue'
import TimeChart from '../components/TimeChart.vue'

const router = useRouter()
const loading = ref(true)
const loadingTimeline = ref(false)
const error = ref('')
const summary = ref<DashboardSummary | null>(null)
const timeline = ref<TimelinePoint[]>([])
const severityDist = ref<{ severity: string; count: number }[]>([])
const topSources = ref<{ source: string; count: number }[]>([])
const topErrors = ref<{ fingerprint: string; sample: string; count: number; status?: string }[]>([])
type TimelineMode = 'all' | 'day' | 'hour'
const bucket = ref<TimelineMode>('all')
/** Bucket width actually used (the adaptive "all" view picks its own). */
const pointBucket = ref<string>('day')
const timelineLabel = computed(() => {
  if (bucket.value === 'day') return 'last 60 days of data'
  if (bucket.value === 'hour') return 'last 60 hours of data'
  return `all data · per ${pointBucket.value}`
})

const chartPoints = computed(() =>
  timeline.value.map((p) => ({
    key: p.bucket,
    total: p.total,
    errors: p.errors,
    xLabel:
      pointBucket.value === 'hour' || pointBucket.value === 'minute'
        ? formatShortDateTime(p.bucket)
        : pointBucket.value === 'month'
          ? formatMonth(p.bucket)
          : formatShortDate(p.bucket),
  })),
)

const errorShare = computed(() => {
  const s = summary.value
  if (!s || s.total === 0) return '—'
  return `${((s.errors / s.total) * 100).toFixed(1)}% of total`
})

/** "01 May → 31 Jan", with years when the range spans calendar years. */
const dateRange = computed(() => {
  const s = summary.value
  if (!s?.first_seen) return ''
  const from = new Date(s.first_seen)
  const to = s.last_seen ? new Date(s.last_seen) : from
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) {
    return `${formatShortDate(s.first_seen)} → ${formatShortDate(s.last_seen ?? s.first_seen)}`
  }
  const sameYear = from.getFullYear() === to.getFullYear()
  const fmt = (d: Date) =>
    d.toLocaleDateString('en-GB', sameYear ? { day: '2-digit', month: 'short' } : { day: '2-digit', month: 'short', year: 'numeric' })
  return `${fmt(from)} → ${fmt(to)}`
})

const warningShare = computed(() => {
  const s = summary.value
  if (!s || s.total === 0) return '—'
  return `${((s.warnings / s.total) * 100).toFixed(1)}% of total`
})

const maxSeverity = computed(() => Math.max(1, ...severityDist.value.map((r) => r.count)))
const maxSource = computed(() => Math.max(1, ...topSources.value.map((r) => r.count)))

const mutedNote = computed(() => {
  const hidden = topErrors.value.filter((r) => r.status && r.status !== 'open').length
  return hidden > 0 ? `${hidden} group${hidden === 1 ? '' : 's'} already triaged.` : ''
})

function barWidth(count: number, max: number): number {
  return Math.max(3, Math.round((count / max) * 100))
}

function sevColor(sev: string): string {
  switch (sev) {
    case 'ERROR':
      return 'linear-gradient(90deg, var(--danger-strong), var(--danger))'
    case 'FATAL':
    case 'CRITICAL':
      return 'var(--danger-strong)'
    case 'WARN':
    case 'WARNING':
      return 'linear-gradient(90deg, #f59e0b, var(--warning))'
    case 'INFO':
      return 'linear-gradient(90deg, #0284c7, var(--info))'
    case 'DEBUG':
      return 'var(--sev-debug)'
    case 'TRACE':
      return 'var(--sev-trace)'
    default:
      return 'var(--text-3)'
  }
}

function goSeverity(sev: string) {
  router.push({ path: '/logs', query: { severity: sev } })
}

function goSource(source: string) {
  router.push({ path: '/logs', query: { source } })
}

function goErrors() {
  router.push({ path: '/errors' })
}

async function loadTimeline() {
  loadingTimeline.value = true
  try {
    if (bucket.value === 'all') {
      const hist: LogHistogram = (await api.get('/logs/histogram')).data
      timeline.value = hist.points
      pointBucket.value = hist.bucket
    } else {
      timeline.value = (await api.get('/dashboard/timeline', { params: { bucket: bucket.value } })).data
      pointBucket.value = bucket.value
    }
  } finally {
    loadingTimeline.value = false
  }
}

async function setBucket(b: TimelineMode) {
  if (bucket.value === b) return
  bucket.value = b
  await loadTimeline()
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [s, sev, src, err] = await Promise.all([
      api.get('/dashboard/summary'),
      api.get('/dashboard/severity-distribution'),
      api.get('/dashboard/top-sources'),
      api.get('/dashboard/top-errors', { params: { limit: 8 } }),
    ])
    summary.value = s.data
    severityDist.value = sev.data
    topSources.value = src.data
    topErrors.value = err.data
    await loadTimeline()
  } catch {
    error.value = 'Could not load dashboard data. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

function refresh() {
  void loadAll()
}

onMounted(loadAll)
</script>
