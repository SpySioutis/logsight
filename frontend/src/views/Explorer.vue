<template>
  <PageHeader title="Log Explorer">
    <template #subtitle>
      <template v-if="page">{{ formatNumber(page.total) }} entries match</template>
      <template v-else>Search and filter every stored log entry</template>
    </template>
    <template #actions>
      <input
        v-model="saveName"
        type="text"
        placeholder="Save current filter as…"
        style="width: 210px"
        @keyup.enter="saveCurrentFilter"
      />
      <button class="subtle sm" :disabled="!saveName.trim()" @click="saveCurrentFilter">
        <AppIcon name="filters" :size="14" /> Save filter
      </button>
    </template>
  </PageHeader>

  <div v-if="error" class="alert"><AppIcon name="alert-circle" :size="16" />{{ error }}</div>
  <div v-if="savedNotice" class="notice"><AppIcon name="check-circle" :size="16" />{{ savedNotice }}</div>

  <div class="panel">
    <FilterBar :model-value="query" :sources="facets.sources" :services="facets.services" @update:model-value="onQueryUpdate" @clear="resetQuery" />

    <div class="active-chips">
      <span v-for="chip in activeChips" :key="chip.key" class="chip chip-accent">
        {{ chip.label }}
        <button :title="`Remove ${chip.label}`" @click="chip.remove()">
          <AppIcon name="x" :size="12" />
        </button>
      </span>
    </div>

    <div class="toolbar">
      <label class="field" style="flex-direction: row; align-items: center">
        Sort
        <select :value="`${query.sort}:${query.direction}`" @change="onSortChange">
          <option value="timestamp:desc">Newest first</option>
          <option value="timestamp:asc">Oldest first</option>
          <option value="severity:desc">Severity ↓</option>
          <option value="severity:asc">Severity ↑</option>
          <option value="source:asc">Source A–Z</option>
          <option value="service:asc">Service A–Z</option>
          <option value="relevance:desc">Relevance</option>
        </select>
      </label>
      <label class="field" style="flex-direction: row; align-items: center">
        Per page
        <select :value="query.page_size" @change="query.page_size = Number(($event.target as HTMLSelectElement).value); query.page = 1">
          <option v-for="size in PAGE_SIZES" :key="size" :value="size">{{ size }}</option>
        </select>
      </label>
      <span class="spacer"></span>
      <span v-if="loading" class="dim" style="font-size: 12.5px">Loading…</span>
      <a
        class="btn sm subtle"
        :class="{ disabled: !page?.total }"
        :href="exportUrl(query, 'csv')"
        download
        :title="exportTitle"
      ><AppIcon name="download" :size="13" /> CSV</a>
      <a
        class="btn sm subtle"
        :class="{ disabled: !page?.total }"
        :href="exportUrl(query, 'jsonl')"
        download
        :title="exportTitle"
      ><AppIcon name="download" :size="13" /> JSONL</a>
    </div>

    <HistogramBars
      v-if="histogram && histogram.points.length > 1"
      :points="histogram.points"
      :bucket="histogram.bucket"
      :loading="histogramLoading"
      @zoom="zoomTo"
    />

    <TableSkeleton v-if="loading && !page" :rows="8" />
    <template v-else-if="page && page.items.length">
      <LogTable :entries="page.items" :sort="query.sort ?? 'timestamp'" :direction="query.direction ?? 'desc'" @select="selected = $event" @sort="onHeaderSort" />
      <Pagination :page="page.page" :pages="page.pages" :total="page.total" @change="goToPage" />
    </template>
    <EmptyState v-else title="No entries match" icon="search" hint="Adjust the search text, severity toggles or date range." />
  </div>

  <LogDetails :entry="selected" in-explorer @close="selected = null" @filter="onDrawerFilter" />
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  api,
  apiParams,
  exportUrl,
  isoToLocalInput,
  toParams,
  type LogEntry,
  type LogHistogram,
  type LogPage,
  type LogQuery,
} from '../api/client'
import { useSettingsStore } from '../stores/settings'
import { formatNumber, truncate } from '../utils/format'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import FilterBar from '../components/FilterBar.vue'
import HistogramBars from '../components/HistogramBars.vue'
import LogDetails from '../components/LogDetails.vue'
import LogTable from '../components/LogTable.vue'
import PageHeader from '../components/PageHeader.vue'
import Pagination from '../components/Pagination.vue'
import TableSkeleton from '../components/TableSkeleton.vue'

const route = useRoute()
const router = useRouter()
const settings = useSettingsStore()

settings.applyTheme()

const SORT_FIELDS = ['timestamp', 'severity', 'source', 'service', 'relevance']
const PAGE_SIZES = [25, 50, 100, 200, 500]

function initialQuery(): LogQuery {
  const q = route.query
  const severity = q.severity
  return {
    q: typeof q.q === 'string' ? q.q : undefined,
    severity: Array.isArray(severity) ? severity.map(String) : severity ? [String(severity)] : [],
    source: typeof q.source === 'string' ? q.source : undefined,
    service: typeof q.service === 'string' ? q.service : undefined,
    import_id: typeof q.import_id === 'string' ? q.import_id : undefined,
    trace_id: typeof q.trace_id === 'string' ? q.trace_id : undefined,
    request_id: typeof q.request_id === 'string' ? q.request_id : undefined,
    fingerprint: typeof q.fingerprint === 'string' ? q.fingerprint : undefined,
    date_from: typeof q.date_from === 'string' ? q.date_from : undefined,
    date_to: typeof q.date_to === 'string' ? q.date_to : undefined,
    sort: typeof q.sort === 'string' && SORT_FIELDS.includes(q.sort) ? q.sort : 'timestamp',
    direction: q.direction === 'asc' || q.direction === 'desc' ? q.direction : 'desc',
    page: positiveInt(q.page) ?? 1,
    page_size: PAGE_SIZES.includes(positiveInt(q.page_size) ?? 0) ? Number(q.page_size) : settings.pageSize,
  }
}

function positiveInt(value: unknown): number | undefined {
  const n = typeof value === 'string' ? Number(value) : NaN
  return Number.isInteger(n) && n > 0 ? n : undefined
}

const query = reactive<LogQuery>(initialQuery())
const page = ref<LogPage | null>(null)
const loading = ref(false)
const error = ref('')
const selected = ref<LogEntry | null>(null)
const saveName = ref('')
const histogram = ref<LogHistogram | null>(null)
const histogramLoading = ref(false)
const MAX_EXPORT_ROWS = 100000
const exportTitle = computed(() =>
  page.value && page.value.total > MAX_EXPORT_ROWS
    ? `Download the first ${formatNumber(MAX_EXPORT_ROWS)} of ${formatNumber(page.value.total)} matching entries`
    : 'Download all matching entries',
)
const savedNotice = ref('')
const facets = ref<{ severities: string[]; sources: string[]; services: string[] }>({
  severities: [],
  sources: [],
  services: [],
})

interface Chip {
  key: string
  label: string
  remove: () => void
}

const activeChips = computed<Chip[]>(() => {
  const chips: Chip[] = []
  if (query.q) chips.push({ key: 'q', label: `“${truncate(query.q, 32)}”`, remove: () => (query.q = undefined) })
  for (const sev of query.severity ?? []) {
    chips.push({
      key: `sev-${sev}`,
      label: sev,
      remove: () => (query.severity = (query.severity ?? []).filter((s) => s !== sev)),
    })
  }
  if (query.source) chips.push({ key: 'source', label: `source:${truncate(query.source, 24)}`, remove: () => (query.source = undefined) })
  if (query.service) chips.push({ key: 'service', label: `service:${truncate(query.service, 24)}`, remove: () => (query.service = undefined) })
  if (query.trace_id) chips.push({ key: 'trace', label: `trace:${truncate(query.trace_id, 16)}`, remove: () => (query.trace_id = undefined) })
  if (query.request_id) chips.push({ key: 'req', label: `request:${truncate(query.request_id, 16)}`, remove: () => (query.request_id = undefined) })
  if (query.fingerprint) chips.push({ key: 'fp', label: `error group:${query.fingerprint.slice(0, 8)}`, remove: () => (query.fingerprint = undefined) })
  if (query.import_id) chips.push({ key: 'import', label: `import:${truncate(query.import_id, 8)}`, remove: () => (query.import_id = undefined) })
  if (query.date_from) chips.push({ key: 'from', label: `from ${query.date_from}`, remove: () => (query.date_from = undefined) })
  if (query.date_to) chips.push({ key: 'to', label: `to ${query.date_to}`, remove: () => (query.date_to = undefined) })
  return chips
})

let timer: number | undefined

/** Merge child updates into the reactive query in place (never replace it). */
function onQueryUpdate(next: LogQuery) {
  Object.assign(query, next)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/logs', { params: apiParams(query) })
    page.value = res.data
  } catch {
    error.value = 'Could not load log entries. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

let histogramKey = ''
let histogramSeq = 0

/** Reload the histogram only when the filters (not sort/paging) changed. */
async function loadHistogram() {
  const params = apiParams({ ...query, sort: undefined, direction: undefined, page: undefined, page_size: undefined })
  const key = JSON.stringify(params)
  if (key === histogramKey) return
  histogramKey = key
  const seq = ++histogramSeq
  histogramLoading.value = true
  try {
    const res = await api.get('/logs/histogram', { params })
    if (seq === histogramSeq) histogram.value = res.data
  } catch {
    if (seq === histogramSeq) histogram.value = null
  } finally {
    if (seq === histogramSeq) histogramLoading.value = false
  }
}

const BUCKET_STEP: Record<string, (d: Date) => void> = {
  // Buckets are UTC: step with UTC setters (local ones drift across DST
  // and month lengths in non-UTC timezones).
  minute: (d) => d.setUTCMinutes(d.getUTCMinutes() + 1),
  hour: (d) => d.setUTCHours(d.getUTCHours() + 1),
  day: (d) => d.setUTCDate(d.getUTCDate() + 1),
  month: (d) => d.setUTCMonth(d.getUTCMonth() + 1),
}

function zoomTo(bucketStart: string) {
  if (!histogram.value) return
  const end = new Date(bucketStart)
  if (Number.isNaN(end.getTime())) return
  BUCKET_STEP[histogram.value.bucket]?.(end)
  // date_to is inclusive (<=): stop 1 ms before the next bucket starts so
  // entries exactly on that boundary are not pulled into this bucket.
  end.setUTCMilliseconds(end.getUTCMilliseconds() - 1)
  query.date_from = isoToLocalInput(bucketStart)
  query.date_to = isoToLocalInput(end.toISOString(), true)
}

function scheduleReload() {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => {
    query.page = 1
    selected.value = null
    load()
    loadHistogram()
    syncUrl()
  }, 350)
}

watch(
  () => [query.q, query.severity, query.source, query.service, query.trace_id, query.request_id, query.fingerprint, query.import_id, query.date_from, query.date_to, query.page_size, query.sort, query.direction],
  scheduleReload,
  { deep: true },
)

function resetQuery() {
  Object.assign(query, {
    q: undefined,
    severity: [],
    source: undefined,
    service: undefined,
    import_id: undefined,
    trace_id: undefined,
    request_id: undefined,
    fingerprint: undefined,
    date_from: undefined,
    date_to: undefined,
    page: 1,
  })
}

/** "Filter by this value" from the entry drawer: replace that one filter. */
function onDrawerFilter(field: 'service' | 'source' | 'import_id' | 'fingerprint', value: string) {
  query[field] = value
}

function syncUrl() {
  router.replace({ query: toParams(query) as Record<string, string> })
}

function goToPage(p: number) {
  query.page = p
  selected.value = null
  load()
  syncUrl()
}

function onSortChange(event: Event) {
  const [sort, direction] = (event.target as HTMLSelectElement).value.split(':')
  query.sort = sort
  query.direction = direction as 'asc' | 'desc'
}

function onHeaderSort(field: string) {
  if (query.sort === field) {
    query.direction = query.direction === 'asc' ? 'desc' : 'asc'
  } else {
    query.sort = field
    query.direction = field === 'timestamp' ? 'desc' : 'asc'
  }
}

async function saveCurrentFilter() {
  const name = saveName.value.trim()
  if (!name) return
  try {
    await api.post('/filters', {
      name,
      description: null,
      params: {
        q: query.q,
        severity: query.severity,
        source: query.source,
        service: query.service,
        trace_id: query.trace_id,
        request_id: query.request_id,
        fingerprint: query.fingerprint,
        date_from: query.date_from,
        date_to: query.date_to,
        sort: query.sort,
        direction: query.direction,
      },
    })
    savedNotice.value = `Filter "${name}" saved.`
    saveName.value = ''
    setTimeout(() => (savedNotice.value = ''), 3000)
  } catch {
    savedNotice.value = 'Could not save: a filter with this name may already exist.'
  }
}

onMounted(async () => {
  try {
    facets.value = (await api.get('/logs/meta/facets')).data
  } catch {
    facets.value = { severities: [], sources: [], services: [] }
  }
  await Promise.all([load(), loadHistogram()])
})
</script>
