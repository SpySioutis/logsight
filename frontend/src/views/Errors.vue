<template>
  <PageHeader title="Errors" subtitle="Recurring problems, grouped deterministically by message shape">
    <template #actions>
      <div class="segmented" role="tablist" aria-label="Status filter">
        <button :class="{ active: statusFilter === '' }" @click="statusFilter = ''; reload()">All</button>
        <button :class="{ active: statusFilter === 'open' }" @click="statusFilter = 'open'; reload()">Open</button>
        <button :class="{ active: statusFilter === 'acknowledged' }" @click="statusFilter = 'acknowledged'; reload()">Acked</button>
        <button :class="{ active: statusFilter === 'resolved' }" @click="statusFilter = 'resolved'; reload()">Resolved</button>
        <button :class="{ active: statusFilter === 'muted' }" @click="statusFilter = 'muted'; reload()">Muted</button>
      </div>
      <span v-if="!loading" class="chip chip-mono">{{ formatNumber(groups.length) }} groups</span>
    </template>
  </PageHeader>

  <div v-if="error" class="alert"><AppIcon name="alert-circle" :size="16" />{{ error }}</div>

  <div class="panel">
    <TableSkeleton v-if="loading" :rows="6" />
    <template v-else-if="groups.length">
      <div class="table-wrap">
        <table class="grid fixed">
          <thead>
            <tr>
              <th>Representative message</th>
              <th style="width: 110px">Severity</th>
              <th style="width: 140px">Status</th>
              <th style="width: 96px; text-align: right">Count</th>
              <th style="width: 150px">Sources</th>
              <th style="width: 172px">Last seen</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="g in groups"
              :key="g.fingerprint"
              class="rowlink"
              :class="{ 'row-active': activeGroup?.fingerprint === g.fingerprint }"
              @click="openGroup(g)"
            >
              <td class="mono ellipsis" :title="g.sample" style="font-size: 12.5px">{{ truncate(firstLine(g.sample), 140) }}</td>
              <td><SeverityBadge :severity="g.severity" /></td>
              <td><StatusBadge :status="g.status" /></td>
              <td class="mono" style="text-align: right; font-weight: 700; color: var(--danger)">{{ formatNumber(g.count) }}×</td>
              <td class="dim" style="font-size: 12.5px">{{ g.sources.slice(0, 2).join(', ') || '—' }}{{ g.sources.length > 2 ? ` +${g.sources.length - 2}` : '' }}</td>
              <td class="mono dim nowrap" style="font-size: 12px">{{ formatDateTime(g.last_seen) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <EmptyState v-else title="No error groups" icon="check-circle" hint="Error, fatal and critical entries are grouped here once logs are imported." />
  </div>

  <div v-if="activeGroup" class="panel rise">
    <div class="toolbar">
      <SeverityBadge :severity="activeGroup.severity" />
      <strong style="font-size: 14px">Matching entries · {{ formatNumber(groupPage?.total ?? 0) }}</strong>
      <span class="mono faint" style="font-size: 11.5px" :title="activeGroup.fingerprint">fp:{{ truncate(activeGroup.fingerprint, 12) }}</span>
      <span class="spacer"></span>
      <button class="sm" @click="goToExplorer"><AppIcon name="logs" :size="14" /> Open in Explorer</button>
      <button class="sm ghost" @click="closeGroup"><AppIcon name="x" :size="14" /> Close</button>
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
      <button class="primary sm" style="align-self: flex-end" :disabled="saving" @click="saveState">
        <AppIcon name="check" :size="14" /> {{ saving ? 'Saving…' : 'Save' }}
      </button>
      <div v-if="trend.length" class="field">
        <span style="font-size: 12px; color: var(--text-2); font-weight: 550">Last {{ trend.length }} days</span>
        <TrendSpark :points="trend" />
      </div>
    </div>
    <div v-if="stateNotice" class="notice"><AppIcon name="check-circle" :size="16" />{{ stateNotice }}</div>

    <div v-if="groupPage && groupPage.items.length">
      <LogTable :entries="groupPage.items" sort="timestamp" direction="desc" @select="selected = $event" @sort="() => {}" />
      <Pagination :page="groupPage.page" :pages="groupPage.pages" :total="groupPage.total" @change="loadGroupPage" />
    </div>
  </div>

  <LogDetails :entry="selected" @close="selected = null" />
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type ErrorGroup, type ErrorTrendPoint, type LogEntry, type LogPage } from '../api/client'
import { formatDateTime, formatNumber, truncate } from '../utils/format'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import LogDetails from '../components/LogDetails.vue'
import LogTable from '../components/LogTable.vue'
import PageHeader from '../components/PageHeader.vue'
import Pagination from '../components/Pagination.vue'
import SeverityBadge from '../components/SeverityBadge.vue'
import StatusBadge from '../components/StatusBadge.vue'
import TableSkeleton from '../components/TableSkeleton.vue'
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

let openSeq = 0

async function openGroup(g: ErrorGroup) {
  const seq = ++openSeq
  activeGroup.value = g
  selected.value = null
  groupPage.value = null
  trend.value = []
  stateForm.status = g.status
  stateForm.assignee = g.assignee ?? ''
  stateForm.note = g.note ?? ''
  stateNotice.value = ''
  try {
    const [entries, trendRes] = await Promise.all([
      api.get(`/errors/groups/${g.fingerprint}`, { params: { page_size: 25 } }),
      api.get(`/errors/groups/${g.fingerprint}/trend`).catch(() => ({ data: [] })),
    ])
    // Ignore responses for a group the user already navigated away from.
    if (seq !== openSeq) return
    groupPage.value = entries.data
    trend.value = trendRes.data
  } catch {
    if (seq === openSeq) error.value = 'Could not load entries for this error group.'
  }
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
  // Filter by the group's fingerprint: searching the sample text matched
  // only near-identical lines (its timestamp/service tokens became filters).
  router.push({ path: '/logs', query: { fingerprint: activeGroup.value.fingerprint } })
}

onMounted(reload)
</script>

<style scoped>
.row-active td {
  background: var(--accent-soft) !important;
}
.row-active td:first-child {
  box-shadow: inset 3px 0 0 var(--accent);
}
</style>
