<template>
  <div class="page-head">
    <h1>Log Explorer</h1>
    <span class="sub" v-if="page"> {{ formatNumber(page.total) }} entries match </span>
    <span class="spacer" style="flex: 1"></span>
    <input
      v-model="saveName"
      type="text"
      placeholder="Save current filter as…"
      style="width: 220px"
      @keyup.enter="saveCurrentFilter"
    />
    <button :disabled="!saveName.trim()" @click="saveCurrentFilter">Save filter</button>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>
  <div v-if="savedNotice" class="notice">{{ savedNotice }}</div>

  <div class="panel">
    <FilterBar v-model="query" :sources="facets.sources" :services="facets.services" @clear="resetQuery" />
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
        </select>
      </label>
      <label class="field" style="flex-direction: row; align-items: center">
        Per page
        <select :value="query.page_size" @change="query.page_size = Number(($event.target as HTMLSelectElement).value); query.page = 1">
          <option :value="25">25</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
        </select>
      </label>
    </div>

    <div v-if="loading" class="dim">Loading…</div>
    <template v-else-if="page && page.items.length">
      <LogTable :entries="page.items" :sort="query.sort ?? 'timestamp'" :direction="query.direction ?? 'desc'" @select="selected = $event" @sort="onHeaderSort" />
      <Pagination :page="page.page" :pages="page.pages" :total="page.total" @change="goToPage" />
    </template>
    <EmptyState v-else title="No entries match" hint="Adjust the search text, severity toggles or date range." />
  </div>

  <LogDetails :entry="selected" @close="selected = null" />
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, toParams, type LogEntry, type LogPage, type LogQuery } from '../api/client'
import { useSettingsStore } from '../stores/settings'
import { formatNumber } from '../utils/format'
import FilterBar from '../components/FilterBar.vue'
import LogDetails from '../components/LogDetails.vue'
import LogTable from '../components/LogTable.vue'
import Pagination from '../components/Pagination.vue'
import EmptyState from '../components/EmptyState.vue'

const route = useRoute()
const router = useRouter()
const settings = useSettingsStore()

settings.applyTheme()

function initialQuery(): LogQuery {
  const q = route.query
  const severity = q.severity
  return {
    q: typeof q.q === 'string' ? q.q : undefined,
    severity: Array.isArray(severity) ? severity.map(String) : severity ? [String(severity)] : [],
    source: typeof q.source === 'string' ? q.source : undefined,
    service: typeof q.service === 'string' ? q.service : undefined,
    import_id: typeof q.import_id === 'string' ? q.import_id : undefined,
    date_from: typeof q.date_from === 'string' ? q.date_from : undefined,
    date_to: typeof q.date_to === 'string' ? q.date_to : undefined,
    sort: 'timestamp',
    direction: 'desc',
    page: 1,
    page_size: settings.pageSize,
  }
}

const query = reactive<LogQuery>(initialQuery())
const page = ref<LogPage | null>(null)
const loading = ref(false)
const error = ref('')
const selected = ref<LogEntry | null>(null)
const saveName = ref('')
const savedNotice = ref('')
const facets = ref<{ severities: string[]; sources: string[]; services: string[] }>({
  severities: [],
  sources: [],
  services: [],
})

let timer: number | undefined

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/logs', { params: toParams(query) })
    page.value = res.data
  } catch {
    error.value = 'Could not load log entries. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

function scheduleReload() {
  window.clearTimeout(timer)
  timer = window.setTimeout(() => {
    query.page = 1
    selected.value = null
    load()
    router.replace({ query: toParams(query) as Record<string, string> })
  }, 350)
}

watch(
  () => [query.q, query.severity, query.source, query.service, query.date_from, query.date_to, query.page_size, query.sort, query.direction],
  scheduleReload,
  { deep: true },
)

function resetQuery() {
  Object.assign(query, {
    q: undefined,
    severity: [],
    source: undefined,
    service: undefined,
    date_from: undefined,
    date_to: undefined,
    page: 1,
  })
}

function goToPage(p: number) {
  query.page = p
  selected.value = null
  load()
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
        date_from: query.date_from,
        date_to: query.date_to,
        sort: query.sort,
        direction: query.direction,
      },
    })
    savedNotice.value = `Filter "${name}" saved.`
    saveName.value = ''
    setTimeout(() => (savedNotice.value = ''), 3000)
  } catch (e: unknown) {
    savedNotice.value = 'Could not save: a filter with this name may already exist.'
  }
}

onMounted(async () => {
  try {
    facets.value = (await api.get('/logs/meta/facets')).data
  } catch {
    facets.value = { severities: [], sources: [], services: [] }
  }
  await load()
})
</script>
