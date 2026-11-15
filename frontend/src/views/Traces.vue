<template>
  <PageHeader title="Traces" subtitle="Distributed traces correlated across services and time">
    <template #actions>
      <input
        v-model="jumpId"
        type="text"
        placeholder="Jump to trace ID…"
        style="width: 220px; font-family: var(--mono); font-size: 12.5px"
        @keyup.enter="jumpToTrace"
      />
      <button class="sm" :disabled="!jumpId.trim()" @click="jumpToTrace">
        <AppIcon name="arrow-right" :size="14" /> Open
      </button>
    </template>
  </PageHeader>

  <div v-if="error" class="alert"><AppIcon name="alert-circle" :size="16" />{{ error }}</div>

  <div class="panel">
    <TableSkeleton v-if="loading" :rows="6" />
    <template v-else-if="traces.length">
      <div class="table-wrap">
        <table class="grid">
          <thead>
            <tr>
              <th>Trace ID</th>
              <th style="width: 90px; text-align: right">Spans</th>
              <th style="width: 220px">Services</th>
              <th style="width: 170px">Severities</th>
              <th style="width: 172px">Last seen</th>
              <th style="width: 44px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in traces" :key="t.trace_id" class="rowlink" @click="openTrace(t.trace_id)">
              <td class="mono" style="font-size: 12.5px; color: var(--accent-2)" :title="t.trace_id">
                {{ truncate(t.trace_id, 28) }}
              </td>
              <td class="mono" style="text-align: right; font-weight: 700">{{ formatNumber(t.count) }}</td>
              <td>
                <span v-if="t.services.length" class="dim" style="font-size: 12.5px">
                  {{ t.services.slice(0, 3).join(' · ') }}{{ t.services.length > 3 ? ` +${t.services.length - 3}` : '' }}
                </span>
                <span v-else class="faint">—</span>
              </td>
              <td>
                <span style="display: inline-flex; gap: 4px; flex-wrap: wrap">
                  <SeverityBadge v-for="sev in t.severities.slice(0, 3)" :key="sev" :severity="sev" />
                  <span v-if="t.severities.length > 3" class="faint" style="font-size: 11.5px">+{{ t.severities.length - 3 }}</span>
                </span>
              </td>
              <td class="mono dim nowrap" style="font-size: 12px">{{ formatDateTime(t.last_seen) }}</td>
              <td><AppIcon name="chevron-right" :size="15" style="color: var(--text-3)" /></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="faint" style="font-size: 12px; margin: 12px 2px 0">Showing {{ traces.length }} most recent traces.</p>
    </template>
    <EmptyState
      v-else
      title="No traces found"
      icon="traces"
      hint="Traces appear once logs with trace_id or request_id are imported."
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type TraceSummary } from '../api/client'
import { formatDateTime, formatNumber, truncate } from '../utils/format'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import PageHeader from '../components/PageHeader.vue'
import SeverityBadge from '../components/SeverityBadge.vue'
import TableSkeleton from '../components/TableSkeleton.vue'

const router = useRouter()
const traces = ref<TraceSummary[]>([])
const loading = ref(true)
const error = ref('')
const jumpId = ref('')

function openTrace(id: string) {
  router.push(`/traces/${encodeURIComponent(id)}`)
}

function jumpToTrace() {
  const id = jumpId.value.trim()
  if (id) openTrace(id)
}

onMounted(async () => {
  try {
    traces.value = (await api.get('/traces', { params: { limit: 50 } })).data
  } catch {
    error.value = 'Could not load traces. Is the backend reachable?'
  } finally {
    loading.value = false
  }
})
</script>
