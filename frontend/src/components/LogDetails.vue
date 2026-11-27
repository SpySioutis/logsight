<template>
  <div v-if="current">
    <div class="drawer-backdrop" @click="$emit('close')"></div>
    <aside class="drawer" role="dialog" aria-label="Log entry details">
      <div class="drawer-head">
        <SeverityBadge :severity="current.severity" />
        <span class="mono faint" style="font-size: 11.5px">{{ formatDateTime(current.timestamp) }}</span>
        <span class="spacer"></span>
        <button class="ghost sm icon-only" :title="copied ? 'Copied!' : 'Copy entry'" @click="copyEntry">
          <AppIcon :name="copied ? 'check' : 'copy'" :size="15" />
        </button>
        <RouterLink
          v-if="current.trace_id"
          :to="`/traces/${encodeURIComponent(current.trace_id)}`"
          class="btn sm subtle"
          style="text-decoration: none"
        >
          <AppIcon name="traces" :size="13" /> Trace
        </RouterLink>
        <button class="ghost sm icon-only" title="Close (Esc)" @click="$emit('close')">
          <AppIcon name="x" :size="15" />
        </button>
      </div>

      <div class="drawer-body">
        <h3 style="margin-top: 0">Message</h3>
        <pre class="payload">{{ current.message }}</pre>

        <h3>Metadata</h3>
        <dl class="kv">
          <dt>Service</dt>
          <dd>{{ current.service ?? '—' }}</dd>
          <dt>Source</dt>
          <dd class="mono" style="font-size: 12.5px">{{ current.source ?? '—' }}</dd>
          <dt>Import</dt>
          <dd class="mono" style="font-size: 12px">{{ shortId(current.import_id) }}</dd>
          <dt>Trace</dt>
          <dd class="mono" style="font-size: 12px">
            <RouterLink v-if="current.trace_id" :to="`/traces/${encodeURIComponent(current.trace_id)}`">
              {{ current.trace_id }}
            </RouterLink>
            <template v-else>—</template>
          </dd>
          <dt>Request</dt>
          <dd class="mono" style="font-size: 12px">
            <RouterLink v-if="current.request_id" :to="`/traces/${encodeURIComponent(current.request_id)}`">
              {{ current.request_id }}
            </RouterLink>
            <template v-else>—</template>
          </dd>
          <dt>Fingerprint</dt>
          <dd class="mono" style="font-size: 12px">{{ current.fingerprint ?? '—' }}</dd>
          <dt>Entry ID</dt>
          <dd class="mono faint" style="font-size: 11.5px">{{ current.id }}</dd>
        </dl>

        <template v-if="current.attributes && Object.keys(current.attributes).length">
          <h3>Structured attributes</h3>
          <pre class="payload">{{ prettyAttributes }}</pre>
        </template>

        <template v-if="current.raw && current.raw !== current.message">
          <h3>Original line</h3>
          <pre class="payload">{{ current.raw }}</pre>
        </template>

        <h3 class="ctx-head">
          Surrounding lines
          <span class="faint ctx-sub">same import, original file order</span>
          <button v-if="current.id !== entry?.id" class="ghost sm" @click="current = entry">Back to selected</button>
        </h3>
        <div v-if="contextError" class="faint ctx-sub">{{ contextError }}</div>
        <div v-else-if="context" class="ctx">
          <button v-if="context.before.length >= span" class="ghost sm ctx-more" @click="span += 20">Load earlier</button>
          <div
            v-for="row in contextRows"
            :key="row.id"
            class="ctx-row"
            :class="{ anchor: row.id === current.id }"
            @click="row.id !== current.id && (current = row)"
          >
            <span class="ctx-sev" :class="`sev-${row.severity.toLowerCase()}`">{{ shortSeverity(row.severity) }}</span>
            <span class="mono faint ctx-ts">{{ formatTime(row.timestamp) }}</span>
            <span class="mono ctx-msg">{{ row.message }}</span>
          </div>
          <button v-if="context.after.length >= span" class="ghost sm ctx-more" @click="span += 20">Load later</button>
        </div>
        <div v-else class="faint ctx-sub">Loading…</div>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api, type LogContext, type LogEntry } from '../api/client'
import { formatDateTime } from '../utils/format'
import AppIcon from './AppIcon.vue'
import SeverityBadge from './SeverityBadge.vue'

const props = defineProps<{ entry: LogEntry | null }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const copied = ref(false)
/** Entry shown in the drawer: the selected one, or a surrounding line. */
const current = ref<LogEntry | null>(props.entry)
const context = ref<LogContext | null>(null)
const contextError = ref('')
const span = ref(8)
const prettyAttributes = computed(() => JSON.stringify(current.value?.attributes ?? {}, null, 2))
const contextRows = computed(() =>
  context.value ? [...context.value.before, context.value.entry, ...context.value.after] : [],
)

watch(
  () => props.entry,
  (next) => {
    current.value = next
    span.value = 8
  },
)

let contextSeq = 0
watch(
  [() => current.value?.id, span],
  async ([id]) => {
    const seq = ++contextSeq
    contextError.value = ''
    if (!id) {
      context.value = null
      return
    }
    if (context.value?.entry.id !== id) context.value = null
    try {
      const res = await api.get(`/logs/${encodeURIComponent(id)}/context`, {
        params: { before: span.value, after: span.value },
      })
      if (seq === contextSeq) context.value = res.data
    } catch {
      if (seq === contextSeq) contextError.value = 'Could not load surrounding lines.'
    }
  },
  { immediate: true },
)

function shortSeverity(severity: string): string {
  return severity.length <= 5 ? severity : severity.slice(0, 4)
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleTimeString('en-GB')
}

function shortId(id: string): string {
  return id.length > 13 ? `${id.slice(0, 8)}…` : id
}

async function copyEntry() {
  const entry = current.value
  if (!entry) return
  const text = [
    `timestamp: ${entry.timestamp ?? 'n/a'}`,
    `severity: ${entry.severity}`,
    `service: ${entry.service ?? 'n/a'}`,
    `source: ${entry.source ?? 'n/a'}`,
    `trace_id: ${entry.trace_id ?? 'n/a'}`,
    `request_id: ${entry.request_id ?? 'n/a'}`,
    `message: ${entry.message}`,
  ].join('\n')
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    copied.value = false
  }
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.entry) emit('close')
}

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<style scoped>
.ctx-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
.ctx-head button { margin-left: auto; }
.ctx-sub { font-size: 11.5px; font-weight: 400; }
.ctx { border: 1px solid var(--border-soft); border-radius: 8px; overflow: hidden; font-size: 12px; }
.ctx-row {
  display: grid;
  grid-template-columns: 44px 70px 1fr;
  gap: 8px;
  padding: 4px 10px;
  border-top: 1px solid var(--border-soft);
  cursor: pointer;
}
.ctx-row:first-child { border-top: 0; }
.ctx-row:hover { background: var(--bg-3); }
.ctx-row.anchor { background: var(--accent-soft); cursor: default; box-shadow: inset 3px 0 0 var(--accent); }
.ctx-msg { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ctx-sev { font-size: 10.5px; font-weight: 650; letter-spacing: 0.02em; color: var(--text-3); }
.ctx-sev.sev-error, .ctx-sev.sev-fatal, .ctx-sev.sev-critical { color: var(--danger); }
.ctx-sev.sev-warn, .ctx-sev.sev-warning { color: var(--sev-warn, #fbbf24); }
.ctx-more { width: 100%; border-radius: 0; justify-content: center; font-size: 11.5px; }
</style>
