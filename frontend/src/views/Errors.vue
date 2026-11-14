<template>
  <div class="page-head">
    <h1>Error Analysis</h1>
    <span class="sub">recurring problems, grouped deterministically by message shape</span>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>

  <div class="panel">
    <div v-if="loading" class="dim">Loading…</div>
    <template v-else-if="groups.length">
      <table class="grid">
        <thead>
          <tr>
            <th>Representative message</th>
            <th style="width: 90px">Severity</th>
            <th style="width: 90px; text-align: right">Count</th>
            <th style="width: 130px">Sources</th>
            <th style="width: 170px">Last seen</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="g in groups"
            :key="g.fingerprint"
            class="rowlink"
            @click="openGroup(g)"
          >
            <td class="mono ellipsis" :title="g.sample">{{ truncate(g.sample, 140) }}</td>
            <td><SeverityBadge :severity="g.severity" /></td>
            <td class="mono" style="text-align: right">{{ formatNumber(g.count) }}×</td>
            <td class="dim">{{ g.sources.slice(0, 2).join(', ') || '—' }}{{ g.sources.length > 2 ? ` +${g.sources.length - 2}` : '' }}</td>
            <td class="mono dim nowrap">{{ formatDateTime(g.last_seen) }}</td>
          </tr>
        </tbody>
      </table>
    </template>
    <EmptyState v-else title="No error groups" hint="Error, fatal and critical entries are grouped here once logs are imported." />
  </div>

  <div v-if="activeGroup" class="panel">
    <div class="toolbar">
      <h2 style="margin: 0">Matching entries · {{ formatNumber(groupPage?.total ?? 0) }}</h2>
      <span class="spacer"></span>
      <RouterLink :to="{ path: '/logs', query: {} }" @click.prevent="goToExplorer">
        <button>Open in Explorer</button>
      </RouterLink>
      <button @click="activeGroup = null; groupPage = null">Close</button>
    </div>
    <div v-if="groupPage && groupPage.items.length">
      <LogTable :entries="groupPage.items" sort="timestamp" direction="desc" @select="selected = $event" @sort="() => {}" />
      <Pagination :page="groupPage.page" :pages="groupPage.pages" :total="groupPage.total" @change="loadGroupPage" />
    </div>
  </div>

  <LogDetails :entry="selected" @close="selected = null" />
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api, type ErrorGroup, type LogEntry, type LogPage } from '../api/client'
import { formatDateTime, formatNumber, truncate } from '../utils/format'
import EmptyState from '../components/EmptyState.vue'
import LogDetails from '../components/LogDetails.vue'
import LogTable from '../components/LogTable.vue'
import Pagination from '../components/Pagination.vue'
import SeverityBadge from '../components/SeverityBadge.vue'

const router = useRouter()
const loading = ref(true)
const error = ref('')
const groups = ref<ErrorGroup[]>([])
const activeGroup = ref<ErrorGroup | null>(null)
const groupPage = ref<LogPage | null>(null)
const selected = ref<LogEntry | null>(null)

async function openGroup(g: ErrorGroup) {
  activeGroup.value = g
  selected.value = null
  const res = await api.get(`/errors/groups/${g.fingerprint}`, { params: { page_size: 25 } })
  groupPage.value = res.data
}

async function loadGroupPage(p: number) {
  if (!activeGroup.value) return
  const res = await api.get(`/errors/groups/${activeGroup.value.fingerprint}`, {
    params: { page: p, page_size: 25 },
  })
  groupPage.value = res.data
  selected.value = null
}

function goToExplorer() {
  if (!activeGroup.value) return
  router.push({ path: '/logs', query: { q: activeGroup.value.sample.slice(0, 80) } })
}

onMounted(async () => {
  try {
    groups.value = (await api.get('/errors/groups')).data
  } catch {
    error.value = 'Could not load error groups. Is the backend reachable?'
  } finally {
    loading.value = false
  }
})
</script>
