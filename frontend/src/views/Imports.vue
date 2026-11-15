<template>
  <PageHeader title="Imports" subtitle="Upload log files and review import history">
    <template #actions>
      <span v-if="!loading && imports.length" class="chip chip-mono">{{ formatNumber(imports.length) }} files</span>
      <span v-if="!loading && imports.length" class="chip chip-mono">{{ formatNumber(totalParsed) }} entries parsed</span>
    </template>
  </PageHeader>

  <div v-if="error" class="alert"><AppIcon name="alert-circle" :size="16" />{{ error }}</div>
  <div v-if="notice" class="notice"><AppIcon name="check-circle" :size="16" />{{ notice }}</div>

  <div class="panel rise">
    <h2><span class="h2-icon"><AppIcon name="imports" :size="15" /></span> Upload a log file</h2>
    <div
      class="dropzone"
      :class="{ over: dragging }"
      @click="fileInput?.click()"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
    >
      <template v-if="uploading">
        <div class="dz-icon"><AppIcon name="imports" :size="25" /></div>
        <div class="dz-title">Uploading {{ uploadName }}… {{ uploadPct }}%</div>
        <div class="progress-track" style="max-width: 420px; margin: 14px auto 0">
          <div class="progress-fill" :style="{ width: `${uploadPct}%` }"></div>
        </div>
      </template>
      <template v-else>
        <div class="dz-icon"><AppIcon name="imports" :size="25" /></div>
        <div class="dz-title">Drop a file here or click to browse</div>
        <div class="dz-sub">Parsed line-by-line on the server · exact duplicates detected by content hash · limit {{ maxUploadMb }} MB</div>
        <div class="format-pills">
          <span class="chip chip-mono">.log</span>
          <span class="chip chip-mono">.txt</span>
          <span class="chip chip-mono">.jsonl</span>
          <span class="chip chip-mono">.json</span>
          <span class="chip chip-mono">.csv</span>
          <span class="chip chip-mono">.gz</span>
          <span class="chip chip-mono">.zip</span>
        </div>
      </template>
    </div>
    <input ref="fileInput" type="file" accept=".log,.txt,.jsonl,.ndjson,.json,.csv,.gz,.zip" hidden @change="onPicked" />
    <p class="faint" style="font-size: 12px; margin: 12px 2px 0">
      Plain text (incl. syslog + stacktraces), JSON Lines, structured JSON and CSV. Gzip and zip bundles accepted.
    </p>
  </div>

  <div class="panel rise rise-1">
    <div class="chart-card-head" style="margin-bottom: 10px">
      <h2 style="margin: 0"><span class="h2-icon"><AppIcon name="history" :size="15" /></span> Import history</h2>
      <span class="spacer"></span>
      <button class="sm ghost" title="Refresh history" @click="refresh"><AppIcon name="refresh" :size="14" /> Refresh</button>
    </div>
    <TableSkeleton v-if="loading" :rows="5" />
    <template v-else-if="imports.length">
      <div class="table-wrap">
        <table class="grid">
          <thead>
            <tr>
              <th>File</th>
              <th style="width: 90px">Format</th>
              <th style="width: 120px">Status</th>
              <th style="width: 110px; text-align: right">Parsed</th>
              <th style="width: 120px; text-align: right">Skipped</th>
              <th style="width: 172px">Imported at</th>
              <th style="width: 190px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="imp in imports" :key="imp.id">
              <td class="ellipsis" :title="`${imp.filename} (${formatBytes(imp.file_size)})`" style="max-width: 320px">
                <AppIcon name="file" :size="14" style="color: var(--text-3); vertical-align: -2px; margin-right: 6px" />{{ imp.filename }}
                <span class="dim">· {{ formatBytes(imp.file_size) }}</span>
              </td>
              <td><span class="chip chip-mono">{{ imp.format }}</span></td>
              <td>
                <span :class="['import-status', imp.status]" :title="imp.error_message ?? imp.status">{{ imp.status }}</span>
              </td>
              <td class="mono" style="text-align: right">{{ formatNumber(imp.parsed_count) }}</td>
              <td class="mono dim" style="text-align: right">{{ formatNumber(imp.error_count) }}</td>
              <td class="mono dim nowrap" style="font-size: 12px">{{ formatDateTime(imp.started_at) }}</td>
              <td class="nowrap" style="text-align: right">
                <button class="sm subtle" style="margin-right: 6px" @click="viewImport(imp.id)">
                  <AppIcon name="eye" :size="13" /> View logs
                </button>
                <button class="sm danger icon-only" :title="`Delete ${imp.filename}`" @click="removeImport(imp)">
                  <AppIcon name="trash" :size="13" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <EmptyState v-else title="No imports yet" icon="package" hint="Upload your first log file above to get started." />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type ImportRecord } from '../api/client'
import { formatBytes, formatDateTime, formatNumber } from '../utils/format'
import AppIcon from '../components/AppIcon.vue'
import EmptyState from '../components/EmptyState.vue'
import PageHeader from '../components/PageHeader.vue'
import TableSkeleton from '../components/TableSkeleton.vue'

const router = useRouter()
const imports = ref<ImportRecord[]>([])
const loading = ref(true)
const error = ref('')
const notice = ref('')
const uploading = ref(false)
const uploadPct = ref(0)
const uploadName = ref('')
const dragging = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const maxUploadMb = import.meta.env.VITE_MAX_UPLOAD_MB ?? '1024'

const totalParsed = computed(() => imports.value.reduce((sum, i) => sum + i.parsed_count, 0))

async function refresh() {
  loading.value = true
  try {
    imports.value = (await api.get('/imports')).data
  } catch {
    error.value = 'Could not load imports. Is the backend reachable?'
  } finally {
    loading.value = false
  }
}

async function upload(file: File) {
  uploading.value = true
  uploadPct.value = 0
  uploadName.value = file.name
  error.value = ''
  notice.value = ''
  const form = new FormData()
  form.append('file', file)
  try {
    const res = await api.post('/imports/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (e.total) uploadPct.value = Math.round((e.loaded / e.total) * 100)
      },
    })
    const record = res.data as ImportRecord
    if (record.duplicate) {
      notice.value = `"${file.name}" is identical to a previous import and was skipped as a duplicate.`
    } else {
      notice.value = `Imported ${formatNumber(record.parsed_count)} entries from "${file.name}".`
    }
    await refresh()
  } catch (e: unknown) {
    error.value = axiosMessage(e)
  } finally {
    uploading.value = false
  }
}

function axiosMessage(e: unknown): string {
  const err = e as { response?: { status?: number; data?: { detail?: string } } }
  if (err.response?.status === 413) return 'File exceeds the upload size limit.'
  if (err.response?.data?.detail) return String(err.response.data.detail)
  return 'Upload failed. Is the backend reachable?'
}

function onPicked(event: Event) {
  const files = (event.target as HTMLInputElement).files
  if (files?.length) upload(files[0])
}

function onDrop(event: DragEvent) {
  dragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) upload(file)
}

function viewImport(id: string) {
  router.push({ path: '/logs', query: { import_id: id } })
}

async function removeImport(imp: ImportRecord) {
  if (!window.confirm(`Delete import "${imp.filename}" and all its log entries?`)) return
  await api.delete(`/imports/${imp.id}`)
  await refresh()
}

onMounted(refresh)
</script>
