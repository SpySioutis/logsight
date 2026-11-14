<template>
  <div class="page-head">
    <h1>Dashboard</h1>
    <span class="sub" v-if="summary">covering {{ formatNumber(summary.total) }} stored entries</span>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>

  <div v-if="!loading && summary && summary.total === 0">
    <EmptyState title="No logs yet">
      Import a log file to see statistics here.
      <RouterLink to="/imports">Go to Sources / Imports</RouterLink> to upload your first file.
    </EmptyState>
  </div>

  <template v-else>
    <div class="stats" v-if="summary">
      <StatCard label="Total entries" :value="summary.total" />
      <StatCard label="Errors" :value="summary.errors" tone="danger" />
      <StatCard label="Warnings" :value="summary.warnings" tone="warn" />
      <StatCard label="Informational" :value="summary.info" />
      <StatCard label="Critical" :value="summary.critical" tone="danger" />
      <StatCard label="Active sources" :value="summary.sources" />
    </div>

    <div class="panel">
      <h2>Logs over time</h2>
      <div class="toolbar" style="margin-bottom: 8px">
        <button :class="{ primary: bucket === 'day' }" @click="bucket = 'day'; loadTimeline()">Day</button>
        <button :class="{ primary: bucket === 'hour' }" @click="bucket = 'hour'; loadTimeline()">Hour</button>
      </div>
      <TimeChart v-if="timeline.length" :points="chartPoints" label="Log volume over time" show-errors />
      <EmptyState v-else title="No timeline data" hint="Entries without timestamps are counted but cannot be plotted." />
    </div>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; margin-top: 14px">
      <div class="panel">
        <h2>Severity distribution</h2>
        <table class="grid" v-if="severityDist.length">
          <tbody>
            <tr v-for="row in severityDist" :key="row.severity">
              <td><SeverityBadge :severity="row.severity" /></td>
              <td class="mono" style="text-align: right">{{ formatNumber(row.count) }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else title="Nothing here yet" />
      </div>

      <div class="panel">
        <h2>Most active sources</h2>
        <table class="grid" v-if="topSources.length">
          <tbody>
            <tr v-for="row in topSources" :key="row.source">
              <td class="ellipsis" :title="row.source">{{ row.source }}</td>
              <td class="mono" style="text-align: right">{{ formatNumber(row.count) }}</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else title="Nothing here yet" />
      </div>

      <div class="panel">
        <h2>Most frequent errors</h2>
        <table class="grid" v-if="topErrors.length">
          <tbody>
            <tr v-for="row in topErrors" :key="row.fingerprint">
              <td class="mono ellipsis" :title="row.sample">{{ truncate(row.sample, 90) }}</td>
              <td class="mono nowrap" style="text-align: right">{{ formatNumber(row.count) }}×</td>
            </tr>
          </tbody>
        </table>
        <EmptyState v-else title="No errors recorded" hint="Error and fatal entries will appear here." />
      </div>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, type DashboardSummary, type TimelinePoint } from '../api/client'
import { formatNumber, formatShortDate, truncate } from '../utils/format'
import EmptyState from '../components/EmptyState.vue'
import SeverityBadge from '../components/SeverityBadge.vue'
import StatCard from '../components/StatCard.vue'
import TimeChart from '../components/TimeChart.vue'

const loading = ref(true)
const error = ref('')
const summary = ref<DashboardSummary | null>(null)
const timeline = ref<TimelinePoint[]>([])
const severityDist = ref<{ severity: string; count: number }[]>([])
const topSources = ref<{ source: string; count: number }[]>([])
const topErrors = ref<{ fingerprint: string; sample: string; count: number }[]>([])
const bucket = ref<'day' | 'hour'>('day')

const chartPoints = computed(() =>
  timeline.value.map((p) => ({
    key: p.bucket,
    total: p.total,
    errors: p.errors,
    xLabel: formatShortDate(p.bucket),
  })),
)

async function loadTimeline() {
  timeline.value = (await api.get('/dashboard/timeline', { params: { bucket: bucket.value } })).data
}

onMounted(async () => {
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
  } catch (e) {
    error.value = 'Could not load dashboard data. Is the backend reachable?'
  } finally {
    loading.value = false
  }
})
</script>
