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
        <template v-if="uploadPct < 100">
          <div class="dz-title">Uploading {{ uploadName }}… {{ uploadPct }}%</div>
          <div v-if="queueTotal > 1" class="dz-sub">file {{ queueIndex }} of {{ queueTotal }}</div>
          <div class="progress-track" style="max-width: 420px; margin: 14px auto 0">
            <div class="progress-fill" :style="{ width: `${uploadPct}%` }"></div>
          </div>
        </template>
        <template v-else-if="ownPct !== null">
          <div class="dz-title">Parsing {{ uploadName }}… {{ ownPct }}%</div>
          <div class="dz-sub">
            {{ formatNumber(ownParsed) }} of {{ formatNumber(ownTotal) }} lines<template v-if="queueTotal > 1"> · file {{ queueIndex }} of {{ queueTotal }}</template>
          </div>
          <div class="progress-track" style="max-width: 420px; margin: 14px auto 0">
            <div class="progress-fill" :style="{ width: `${ownPct}%` }"></div>
          </div>
        </template>
        <template v-else>
          <div class="dz-title">Upload received — starting parse…</div>
          <div v-if="queueTotal > 1" class="dz-sub">file {{ queueIndex }} of {{ queueTotal }}</div>
          <div class="progress-track" style="max-width: 420px; margin: 14px auto 0">
            <div class="progress-fill indeterminate"></div>
          </div>
        </template>
      </template>
      <template v-else>
        <div class="dz-icon"><AppIcon name="imports" :size="25" /></div>
        <div class="dz-title">Drop files here or click to browse</div>
        <div class="dz-sub">Parsed line-by-line on the server · exact duplicates detected by content hash · limit {{ maxUploadMb }} MB</div>
        <div class="format-pills">
          <span class="chip chip-mono">.log</span>
          <span class="chip chip-mono">.txt</span>
          <span class="chip chip-mono">.jsonl</span>
          <span class="chip chip-mono">.ndjson</span>
          <span class="chip chip-mono">.json</span>
          <span class="chip chip-mono">.csv</span>
          <span class="chip chip-mono">.gz</span>
          <span class="chip chip-mono">.zip</span>
        </div>
      </template>
    </div>
    <input ref="fileInput" type="file" accept=".log,.txt,.jsonl,.ndjson,.json,.csv,.gz,.zip" multiple hidden @change="onPicked" />
    <p class="faint" style="font-size: 12px; margin: 12px 2px 0">
      Plain text (incl. syslog + stacktraces), JSON Lines, structured JSON and CSV. Gzip and zip bundles accepted.
    </p>
  </div>

  <div class="panel rise rise-1">
    <div class="chart-card-head" style="margin-bottom: 10px">
      <h2 style="margin: 0"><span class="h2-icon"><AppIcon name="history" :size="15" /></span> Import history</h2>
      <span class="spacer"></span>
      <button class="sm ghost" title="Refresh history" @click="() => refresh()"><AppIcon name="refresh" :size="14" /> Refresh</button>
    </div>
    <TableSkeleton v-if="loading" :rows="5" />
    <template v-else-if="imports.length">
      <div class="table-wrap">
        <table class="grid">
          <thead>
            <tr>
              <th>File</th>
              <th style="width: 90px">Format</th>
              <th style="width: 150px">Status</th>
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
                <template v-if="imp.status === 'processing'">
                  <span class="import-status processing">
                    processing<template v-if="progressPct(imp) !== null"> · {{ progressPct(imp) }}%</template>
                  </span>
                  <div class="progress-track mini" :title="progressTitle(imp)">
                    <div v-if="progressPct(imp) !== null" class="progress-fill" :style="{ width: `${progressPct(imp)}%` }"></div>
                    <div v-else class="progress-fill indeterminate"></div>
                  </div>
                  <div
                    v-if="isStalled(imp)"
                    class="faint nowrap"
                    style="font-size: 11.5px; margin-top: 4px"
                    title="No progress for a while — the import was likely interrupted (e.g. server restart). It is safe to delete it."
                  >
                    stalled? safe to delete
                  </div>
                </template>
                <span v-else :class="['import-status', imp.status]" :title="imp.error_message ?? imp.status">{{ imp.status }}</span>
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
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
const queueIndex = ref(0)
const queueTotal = ref(0)
const maxUploadMb = import.meta.env.VITE_MAX_UPLOAD_MB ?? '1024'

const totalParsed = computed(() => imports.value.reduce((sum, i) => sum + i.parsed_count, 0))

const hasProcessing = computed(() => imports.value.some((i) => i.status === 'processing'))

/** Percent complete for a processing import; null when unknown (e.g. single-doc JSON). Capped at 99 while running. */
function progressPct(imp: ImportRecord): number | null {
  if (imp.status !== 'processing' || imp.total_lines <= 0) return null
  return Math.min(99, Math.floor((imp.parsed_count / imp.total_lines) * 100))
}

function progressTitle(imp: ImportRecord): string {
  if (imp.total_lines > 0) return `${formatNumber(imp.parsed_count)} of ${formatNumber(imp.total_lines)} lines`
  return `${formatNumber(imp.parsed_count)} entries parsed so far`
}

/** A processing row that never reported any total is almost certainly orphaned (e.g. server restart mid-import). */
const STALLED_MS = 5 * 60 * 1000
function isStalled(imp: ImportRecord): boolean {
  if (imp.status !== 'processing' || imp.parsed_count > 0 || imp.total_lines > 0) return false
  if (!imp.started_at) return false
  return Date.now() - new Date(imp.started_at).getTime() > STALLED_MS
}

/** Own upload's live server-side progress (matched by filename while parsing). */
const ownProcessing = computed(
  () =>
    imports.value.find((i) => i.status === 'processing' && i.filename === uploadName.value) ??
    imports.value.find((i) => i.status === 'processing'),
)
const ownPct = computed(() => (ownProcessing.value ? progressPct(ownProcessing.value) : null))
const ownParsed = computed(() => ownProcessing.value?.parsed_count ?? 0)
const ownTotal = computed(() => ownProcessing.value?.total_lines ?? 0)

let pollTimer: number | undefined
function ensurePolling() {
  if (pollTimer !== undefined) return
  pollTimer = window.setInterval(() => {
    void refresh(true)
  }, 2500)
}
function maybeStopPolling() {
  if (!uploading.value && !hasProcessing.value && pollTimer !== undefined) {
    window.clearInterval(pollTimer)
    pollTimer = undefined
  }
}
watch(hasProcessing, (active) => {
  if (active) ensurePolling()
  else maybeStopPolling()
})

async function refresh(silent = false) {
  if (!silent) loading.value = true
  try {
    imports.value = (await api.get('/imports')).data
  } catch {
    error.value = 'Could not load imports. Is the backend reachable?'
  } finally {
    if (!silent) loading.value = false
  }
}

type Outcome = { ok: true; text: string } | { ok: false; text: string }

async function uploadOne(file: File): Promise<Outcome> {
  uploadPct.value = 0
  uploadName.value = file.name
  const form = new FormData()
  form.append('file', file)
  try {
    const res = await api.post('/imports/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      // The request stays open for the whole (synchronous) parse, which can
      // take far longer than the default 120 s for large files.
      timeout: 0,
      onUploadProgress: (e) => {
        if (e.total) uploadPct.value = Math.round((e.loaded / e.total) * 100)
      },
    })
    const record = res.data as ImportRecord
    if (record.duplicate) {
      return { ok: true, text: `"${file.name}" is identical to a previous import and was skipped as a duplicate.` }
    }
    return { ok: true, text: `Imported ${formatNumber(record.parsed_count)} entries from "${file.name}".` }
  } catch (e: unknown) {
    return { ok: false, text: `${file.name}: ${axiosMessage(e)}` }
  }
}

/** Files waiting to be uploaded; drops during an upload are appended. */
const pending: File[] = []

/** Upload files one after another (imports are processed synchronously). */
async function uploadAll(files: File[]) {
  if (!files.length) return
  pending.push(...files)
  queueTotal.value += files.length
  if (uploading.value) return // the running loop picks them up
  uploading.value = true
  error.value = ''
  notice.value = ''
  queueIndex.value = 0
  ensurePolling()
  const done: string[] = []
  const failed: string[] = []
  try {
    let file: File | undefined
    while ((file = pending.shift())) {
      queueIndex.value += 1
      const outcome = await uploadOne(file)
      ;(outcome.ok ? done : failed).push(outcome.text)
      void refresh(true)
    }
  } finally {
    const total = queueTotal.value
    uploading.value = false
    queueTotal.value = 0
    await refresh(true)
    maybeStopPolling()
    notice.value = total === 1 ? done.join('') : done.length ? `${done.length} of ${total} files imported. ${done.join(' ')}` : ''
    error.value = failed.join(' · ')
  }
}

function axiosMessage(e: unknown): string {
  const err = e as { response?: { status?: number; data?: { detail?: string } } }
  if (err.response?.status === 413) return 'File exceeds the upload size limit.'
  if (err.response?.data?.detail) return String(err.response.data.detail)
  return 'Upload failed. Is the backend reachable?'
}

function onPicked(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  // Reset so picking the same file again still fires "change".
  input.value = ''
  void uploadAll(files)
}

function onDrop(event: DragEvent) {
  dragging.value = false
  void uploadAll(Array.from(event.dataTransfer?.files ?? []))
}

function viewImport(id: string) {
  router.push({ path: '/logs', query: { import_id: id } })
}

async function removeImport(imp: ImportRecord) {
  if (!window.confirm(`Delete import "${imp.filename}" and all its log entries?`)) return
  error.value = ''
  try {
    await api.delete(`/imports/${imp.id}`)
  } catch {
    error.value = `Could not delete "${imp.filename}".`
  }
  await refresh(true)
}

onMounted(refresh)
onUnmounted(() => {
  if (pollTimer !== undefined) window.clearInterval(pollTimer)
})
</script>
