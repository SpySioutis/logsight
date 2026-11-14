<template>
  <div class="page-head">
    <h1>Saved Filters</h1>
    <span class="sub">reusable search and filter combinations</span>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>
  <div v-if="notice" class="notice">{{ notice }}</div>

  <div class="panel">
    <h2>{{ editing ? 'Edit filter' : 'New filter' }}</h2>
    <div class="filterbar">
      <label class="field" style="min-width: 200px">
        Name
        <input v-model="form.name" type="text" placeholder="e.g. api errors today" />
      </label>
      <label class="field" style="flex: 1; min-width: 220px">
        Description
        <input v-model="form.description" type="text" placeholder="optional" />
      </label>
    </div>
    <FilterBar v-model="form.params" @clear="form.params = {}" />
    <div class="toolbar">
      <button class="primary" :disabled="!form.name.trim()" @click="save">
        {{ editing ? 'Update' : 'Create' }}
      </button>
      <button v-if="editing" @click="cancelEdit">Cancel</button>
    </div>
  </div>

  <div class="panel">
    <h2>Stored filters</h2>
    <div v-if="loading" class="dim">Loading…</div>
    <template v-else-if="filters.length">
      <table class="grid">
        <thead>
          <tr>
            <th>Name</th>
            <th>Criteria</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in filters" :key="f.id">
            <td>
              <strong>{{ f.name }}</strong>
              <div v-if="f.description" class="dim">{{ f.description }}</div>
            </td>
            <td class="mono dim">{{ describe(f.params) }}</td>
            <td class="nowrap">
              <button @click="applyFilter(f)" style="margin-right: 6px">Apply</button>
              <button @click="startEdit(f)" style="margin-right: 6px">Edit</button>
              <button class="danger" @click="removeFilter(f)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
    <EmptyState v-else title="No saved filters" hint="Create one above, or save the current Explorer view with the “Save filter” field." />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type LogQuery, type SavedFilter } from '../api/client'
import EmptyState from '../components/EmptyState.vue'
import FilterBar from '../components/FilterBar.vue'

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
  window.scrollTo({ top: 0 })
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
