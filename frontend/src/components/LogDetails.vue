<template>
  <div v-if="entry">
    <div class="drawer-backdrop" @click="$emit('close')"></div>
    <aside class="drawer" role="dialog" aria-label="Log entry details">
      <div class="toolbar">
        <h2 style="margin: 0">Log entry</h2>
        <span class="spacer"></span>
        <button @click="copyEntry">{{ copied ? 'Copied' : 'Copy' }}</button>
        <button @click="$emit('close')">Close</button>
      </div>

      <SeverityBadge :severity="entry.severity" />

      <dl class="kv">
        <dt>Timestamp</dt>
        <dd class="mono">{{ formatDateTime(entry.timestamp) }}</dd>
        <dt>Service</dt>
        <dd>{{ entry.service ?? '—' }}</dd>
        <dt>Source</dt>
        <dd>{{ entry.source ?? '—' }}</dd>
        <dt>Import</dt>
        <dd class="mono">{{ entry.import_id }}</dd>
        <dt>Trace</dt>
        <dd class="mono">
          <RouterLink v-if="entry.trace_id" :to="`/traces/${encodeURIComponent(entry.trace_id)}`">
            {{ entry.trace_id }}
          </RouterLink>
          <template v-else>—</template>
        </dd>
        <dt>Request</dt>
        <dd class="mono">
          <RouterLink v-if="entry.request_id" :to="`/traces/${encodeURIComponent(entry.request_id)}`">
            {{ entry.request_id }}
          </RouterLink>
          <template v-else>—</template>
        </dd>
        <dt>Fingerprint</dt>
        <dd class="mono">{{ entry.fingerprint ?? '—' }}</dd>
      </dl>

      <h3>Message</h3>
      <pre class="payload">{{ entry.message }}</pre>

      <template v-if="entry.attributes && Object.keys(entry.attributes).length">
        <h3>Structured attributes</h3>
        <pre class="payload">{{ prettyAttributes }}</pre>
      </template>

      <template v-if="entry.raw && entry.raw !== entry.message">
        <h3>Original line</h3>
        <pre class="payload">{{ entry.raw }}</pre>
      </template>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import type { LogEntry } from '../api/client'
import { formatDateTime } from '../utils/format'
import SeverityBadge from './SeverityBadge.vue'

const props = defineProps<{ entry: LogEntry | null }>()
defineEmits<{ (e: 'close'): void }>()

const copied = ref(false)
const prettyAttributes = computed(() => JSON.stringify(props.entry?.attributes ?? {}, null, 2))

async function copyEntry() {
  if (!props.entry) return
  const text = [
    `timestamp: ${props.entry.timestamp ?? 'n/a'}`,
    `severity: ${props.entry.severity}`,
    `service: ${props.entry.service ?? 'n/a'}`,
    `source: ${props.entry.source ?? 'n/a'}`,
    `trace_id: ${props.entry.trace_id ?? 'n/a'}`,
    `request_id: ${props.entry.request_id ?? 'n/a'}`,
    `message: ${props.entry.message}`,
  ].join('\n')
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    copied.value = false
  }
}
</script>

<style scoped>
h3 { font-size: 12.5px; color: var(--text-dim); margin: 16px 0 8px; text-transform: uppercase; letter-spacing: 0.4px; }
</style>
