<template>
  <div class="page-head">
    <h1>Error Analysis</h1>
    <span class="sub">recurring problems, grouped deterministically by message shape</span>
    <span class="spacer" style="flex: 1"></span>
    <label class="field" style="flex-direction: row; align-items: center">
      Status
      <select v-model="statusFilter" @change="reload">
        <option value="">All</option>
        <option value="open">Open</option>
        <option value="acknowledged">Acknowledged</option>
        <option value="resolved">Resolved</option>
        <option value="muted">Muted</option>
      </select>
    </label>
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
            <th style="width: 120px">Status</th>
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
            <td class="mono ellipsis" :title="g.sample">{{ truncate(firstLine(g.sample), 140) }}</td>
            <td><SeverityBadge :severity="g.severity" /></td>
            <td><span :class="['status', g.status]">{{ g.status }}</span></td>
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
      <button @click="closeGroup">Close</button>
    </div>

    <div class="filterbar">
      <label class="field">
        Status
        <select v-model="stateForm.status">
          <option value="open">open</option>
          <option value="acknowledged">acknowledged</option>
          <option value="resolved">resolved</option>
          <option value="muted">muted</option>
        </select>
      </label>
      <label class="field">
        Assignee
        <input v-model="stateForm.assignee" type="text" placeholder="optional" />
      </label>
      <label class="field" style="flex: 1; min-width: 200px">
        Note
        <input v-model="stateForm.note" type="text" placeholder="optional" />
      </label>
      <button class="primary" :disabled="saving" @click="saveState">{{ saving ? 'Saving…' : 'Save' }}</button>
      <div v-if="trend.length" class="field">
        <span style="font-size: 12px; color: var(--text-dim)">Last {{ trend.length }} days</span>
        <TrendSpark :points="trend" />
      </div>
    </div>
    <div v-if="stateNotice" class="notice">{{ stateNotice }}</div>

    <div v-if="groupPage && groupPage.items.length">
      <LogTable :entries="groupPage.items" sort="timestamp" direction="desc" @select="selected = $event" @sort="() => {}" />
      <Pagination :page="groupPage.page" :pages="groupPage.pages" :total="groupPage.total" @change="loadGroupPage" />
    </div>
  </div>

  <LogDetails :entry="selected" @close="selected = null" />
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api, type ErrorGroup, type ErrorTrendPoint, type LogEntry, type LogPage } from '../api/client'
import { formatDateTime, formatNumber, truncate } from '../utils/format'
import EmptyState from '../components/EmptyState.vue'
import LogDetails from '../components/LogDetails.vue'
import LogTable from '../components/LogTable.vue'
import Pagination from '../components/Pagination.vue'
import SeverityBadge from '../components/SeverityBadge.vue'
import TrendSpark from '../components/TrendSpark.vue'

const router = useRouter()
const loading = ref(true)
const error = ref('')
const groups = ref<ErrorGroup[]>([])
const activeGroup = ref<ErrorGroup | null>(null)
const groupPage = ref<LogPage | null>(null)
const selected = ref<LogEntry | null>(null)
const statusFilter = ref('')
const trend = ref<ErrorTrendPoint[]>([])
const saving = ref(false)
const stateNotice = ref('')
const stateForm = reactive({ status: 'open', assignee: '', note: '' })

function firstLine(message: string): string {
  const idx = message.indexOf('\n')
  return idx === -1 ? message : message.slice(0, idx)
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const params = statusFilter.value ? { status: statusFilter.value } : {}
    groups.value = (await api.get('/errors/groups', { params })).data
  } catch {
    error.value = 'Could not load error groups. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

async function openGroup(g: ErrorGroup) {
  activeGroup.value = g
  selected.value = null
  stateForm.status = g.status
  stateForm.assignee = g.assignee ?? ''
  stateForm.note = g.note ?? ''
  stateNotice.value = ''
  const [entries, trendRes] = await Promise.all([
    api.get(`/errors/groups/${g.fingerprint}`, { params: { page_size: 25 } }),
    api.get(`/errors/groups/${g.fingerprint}/trend`).catch(() => ({ data: [] })),
  ])
  groupPage.value = entries.data
  trend.value = trendRes.data
}

function closeGroup() {
  activeGroup.value = null
  groupPage.value = null
  trend.value = []
}

async function loadGroupPage(p: number) {
  if (!activeGroup.value) return
  const res = await api.get(`/errors/groups/${activeGroup.value.fingerprint}`, {
    params: { page: p, page_size: 25 },
  })
  groupPage.value = res.data
  selected.value = null
}

async function saveState() {
  if (!activeGroup.value) return
  saving.value = true
  stateNotice.value = ''
  try {
    const res = await api.put(`/errors/groups/${activeGroup.value.fingerprint}/state`, {
      status: stateForm.status,
      assignee: stateForm.assignee || null,
      note: stateForm.note || null,
    })
    const updated = res.data
    activeGroup.value.status = updated.status
    activeGroup.value.assignee = updated.assignee
    activeGroup.value.note = updated.note
    const row = groups.value.find((g) => g.fingerprint === activeGroup.value?.fingerprint)
    if (row) {
      row.status = updated.status
      row.assignee = updated.assignee
      row.note = updated.note
    }
    stateNotice.value = 'Status saved.'
    setTimeout(() => (stateNotice.value = ''), 2500)
  } catch {
    stateNotice.value = 'Could not save status.'
  } finally {
    saving.value = false
  }
}

function goToExplorer() {
  if (!activeGroup.value) return
  router.push({ path: '/logs', query: { q: firstLine(activeGroup.value.sample).slice(0, 80) } })
}

onMounted(reload)
</script>

<style scoped>
.status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--bg-sunken);
  color: var(--text-dim);
}
.status.open {
  color: var(--danger);
}
.status.acknowledged {
  color: var(--warn);
}
.status.resolved {
  color: var(--ok);
}
.status.muted {
  color: var(--text-dim);
  text-decoration: line-through;
}
</style>
