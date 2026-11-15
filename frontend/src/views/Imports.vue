<template>
  <div class="page-head">
    <h1>Sources / Imports</h1>
    <span class="sub">upload log files and review import history</span>
  </div>

  <div v-if="error" class="alert">{{ error }}</div>
  <div v-if="notice" class="notice">{{ notice }}</div>

  <div class="panel">
    <h2>Upload a log file</h2>
    <p class="dim" style="margin-top: 0">
      Supported: plain text (.log, .txt, incl. syslog + stacktraces), JSON Lines (.jsonl, .ndjson),
      structured JSON (.json), CSV (.csv). Gzip (.gz) and bundles (.zip) accepted.
      Limit: {{ maxUploadMb }} MB. Files are parsed line-by-line on the server.
    </p>
    <div
      class="dropzone"
      :class="{ over: dragging }"
      @click="fileInput?.click()"
      @dragover.prevent="dragging = true"
      @dragleave="dragging = false"
      @drop.prevent="onDrop"
    >
      <template v-if="uploading">
        Uploading {{ uploadName }}… {{ uploadPct }}%
        <progress :value="uploadPct" max="100"></progress>
      </template>
      <template v-else>
        Drop a file here or click to browse
        <br />
        <span class="dim" style="font-size: 12px">exact duplicates are detected by content hash and skipped</span>
      </template>
    </div>
    <input ref="fileInput" type="file" accept=".log,.txt,.jsonl,.ndjson,.json,.csv,.gz,.zip" hidden @change="onPicked" />
  </div>

  <div class="panel">
    <h2>Import history</h2>
    <div v-if="loading" class="dim">Loading…</div>
    <template v-else-if="imports.length">
      <table class="grid">
        <thead>
          <tr>
            <th>File</th>
            <th>Format</th>
            <th>Status</th>
            <th style="text-align: right">Parsed</th>
            <th style="text-align: right">Skipped lines</th>
            <th>Imported at</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="imp in imports" :key="imp.id">
            <td class="ellipsis" :title="`${imp.filename} (${formatBytes(imp.file_size)})`">
              {{ imp.filename }}
              <span class="dim">· {{ formatBytes(imp.file_size) }}</span>
            </td>
            <td class="mono">{{ imp.format }}</td>
            <td>
              <span v-if="imp.status === 'completed'" style="color: var(--ok)">completed</span>
              <span v-else-if="imp.status === 'duplicate'" style="color: var(--warn)">duplicate</span>
              <span v-else-if="imp.status === 'failed'" style="color: var(--danger)" :title="imp.error_message ?? ''">failed</span>
              <span v-else class="dim">{{ imp.status }}</span>
            </td>
            <td class="mono" style="text-align: right">{{ formatNumber(imp.parsed_count) }}</td>
            <td class="mono" style="text-align: right">{{ formatNumber(imp.error_count) }}</td>
            <td class="mono dim nowrap">{{ formatDateTime(imp.started_at) }}</td>
            <td class="nowrap">
              <button @click="viewImport(imp.id)" style="margin-right: 6px">View logs</button>
              <button class="danger" @click="removeImport(imp)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
    <EmptyState v-else title="No imports yet" hint="Upload your first log file above to get started." />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type ImportRecord } from '../api/client'
import { formatBytes, formatDateTime, formatNumber } from '../utils/format'
import EmptyState from '../components/EmptyState.vue'

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
