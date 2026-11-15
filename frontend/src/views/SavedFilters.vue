<template>
  <PageHeader title="Saved Filters" subtitle="Reusable search and filter combinations">
    <template #actions>
      <span v-if="!loading && filters.length" class="chip chip-mono">{{ formatNumber(filters.length) }} stored</span>
    </template>
  </PageHeader>

  <div v-if="error" class="alert"><AppIcon name="alert-circle" :size="16" />{{ error }}</div>
  <div v-if="notice" class="notice"><AppIcon name="check-circle" :size="16" />{{ notice }}</div>

  <div class="panel rise">
    <h2>
      <span class="h2-icon"><AppIcon :name="editing ? 'pencil' : 'plus'" :size="15" /></span>
      {{ editing ? `Edit filter · ${editing.name}` : 'New filter' }}
    </h2>
    <div class="filterbar">
      <label class="field" style="min-width: 220px">
        Name
        <input v-model="form.name" type="text" placeholder="e.g. api errors today" />
      </label>
      <label class="field" style="flex: 1; min-width: 240px">
        Description
        <input v-model="form.description" type="text" placeholder="optional" />
      </label>
    </div>
    <FilterBar v-model="form.params" @clear="form.params = {}" />
    <div class="toolbar" style="margin-bottom: 0">
      <button class="primary sm" :disabled="!form.name.trim()" @click="save">
        <AppIcon :name="editing ? 'check' : 'plus'" :size="14" /> {{ editing ? 'Update' : 'Create' }}
      </button>
      <button v-if="editing" class="sm ghost" @click="cancelEdit">Cancel</button>
    </div>
  </div>

  <div class="panel rise rise-1">
    <h2><span class="h2-icon"><AppIcon name="filters" :size="15" /></span> Stored filters</h2>
    <TableSkeleton v-if="loading" :rows="4" />
    <div v-else-if="filters.length" style="display: flex; flex-direction: column; gap: 10px">
      <div v-for="f in filters" :key="f.id" class="filter-card">
        <span class="fc-icon"><AppIcon name="filters" :size="18" /></span>
        <div class="fc-main">
          <div class="fc-name">{{ f.name }}</div>
          <div v-if="f.description" class="fc-desc">{{ f.description }}</div>
          <div class="fc-criteria">{{ describe(f.params) }}</div>
        </div>
        <div class="fc-actions">
          <button class="sm primary" @click="applyFilter(f)"><AppIcon name="play" :size="13" /> Apply</button>
          <button class="sm" @click="startEdit(f)"><AppIcon name="pencil" :size="13" /> Edit</button>
          <button class="sm danger icon-only" :title="`Delete ${f.name}`" @click="removeFilter(f)">
            <AppIcon name="trash" :size="13" />
          </button>
        </div>
      </div>
    </div>
    <EmptyState v-else title="No saved filters" icon="filters" hint="Create one above, or save the current Explorer view with the “Save filter” field." />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type LogQuery, type SavedFilter } from '../api/client'
import { formatNumber } from '../utils/format'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import FilterBar from '../components/FilterBar.vue'
import PageHeader from '../components/PageHeader.vue'
import TableSkeleton from '../components/TableSkeleton.vue'

const router = useRouter()
const filters = ref<SavedFilter[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const editing = ref<SavedFilter | null>(null)
const form = reactive<{ name: string; description: string; params: LogQuery }>({
  name: '',
  description: '',
  params: {},
})

function describe(params: LogQuery): string {
  const parts: string[] = []
  if (params.q) parts.push(`q="${params.q}"`)
  if (params.severity?.length) parts.push(`severity=${params.severity.join(',')}`)
  if (params.source) parts.push(`source~${params.source}`)
  if (params.service) parts.push(`service~${params.service}`)
  if (params.trace_id) parts.push(`trace=${params.trace_id}`)
  if (params.request_id) parts.push(`request=${params.request_id}`)
  if (params.date_from) parts.push(`from ${params.date_from}`)
  if (params.date_to) parts.push(`to ${params.date_to}`)
  return parts.join(' · ') || 'no criteria'
}

async function refresh() {
  loading.value = true
  try {
    filters.value = (await api.get('/filters')).data
  } catch {
    error.value = 'Could not load saved filters.'
  } finally {
    loading.value = false
  }
}

async function save() {
  error.value = ''
  try {
    if (editing.value) {
      await api.put(`/filters/${editing.value.id}`, {
        name: form.name.trim(),
        description: form.description || null,
        params: form.params,
      })
      notice.value = `Filter "${form.name.trim()}" updated.`
    } else {
      await api.post('/filters', {
        name: form.name.trim(),
        description: form.description || null,
        params: form.params,
      })
      notice.value = `Filter "${form.name.trim()}" created.`
    }
    cancelEdit()
    await refresh()
    setTimeout(() => (notice.value = ''), 3000)
  } catch {
    error.value = 'Could not save: a filter with this name may already exist.'
  }
}

function startEdit(f: SavedFilter) {
  editing.value = f
  form.name = f.name
  form.description = f.description ?? ''
  form.params = { ...(f.params ?? {}) }
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function cancelEdit() {
  editing.value = null
  form.name = ''
  form.description = ''
  form.params = {}
}

function applyFilter(f: SavedFilter) {
  router.push({ path: '/logs', query: { ...(f.params as Record<string, string>) } })
}

async function removeFilter(f: SavedFilter) {
  if (!window.confirm(`Delete filter "${f.name}"?`)) return
  await api.delete(`/filters/${f.id}`)
  await refresh()
}

onMounted(refresh)
</script>
