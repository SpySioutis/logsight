<template>
  <div v-if="entry">
    <div class="drawer-backdrop" @click="$emit('close')"></div>
    <aside class="drawer" role="dialog" aria-label="Log entry details">
      <div class="drawer-head">
        <SeverityBadge :severity="entry.severity" />
        <span class="mono faint" style="font-size: 11.5px">{{ formatDateTime(entry.timestamp) }}</span>
        <span class="spacer"></span>
        <button class="ghost sm icon-only" :title="copied ? 'Copied!' : 'Copy entry'" @click="copyEntry">
          <AppIcon :name="copied ? 'check' : 'copy'" :size="15" />
        </button>
        <RouterLink
          v-if="entry.trace_id"
          :to="`/traces/${encodeURIComponent(entry.trace_id)}`"
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
        <pre class="payload">{{ entry.message }}</pre>

        <h3>Metadata</h3>
        <dl class="kv">
          <dt>Service</dt>
          <dd>{{ entry.service ?? '—' }}</dd>
          <dt>Source</dt>
          <dd class="mono" style="font-size: 12.5px">{{ entry.source ?? '—' }}</dd>
          <dt>Import</dt>
          <dd class="mono" style="font-size: 12px">{{ shortId(entry.import_id) }}</dd>
          <dt>Trace</dt>
          <dd class="mono" style="font-size: 12px">
            <RouterLink v-if="entry.trace_id" :to="`/traces/${encodeURIComponent(entry.trace_id)}`">
              {{ entry.trace_id }}
            </RouterLink>
            <template v-else>—</template>
          </dd>
          <dt>Request</dt>
          <dd class="mono" style="font-size: 12px">
            <RouterLink v-if="entry.request_id" :to="`/traces/${encodeURIComponent(entry.request_id)}`">
              {{ entry.request_id }}
            </RouterLink>
            <template v-else>—</template>
          </dd>
          <dt>Fingerprint</dt>
          <dd class="mono" style="font-size: 12px">{{ entry.fingerprint ?? '—' }}</dd>
          <dt>Entry ID</dt>
          <dd class="mono faint" style="font-size: 11.5px">{{ entry.id }}</dd>
        </dl>

        <template v-if="entry.attributes && Object.keys(entry.attributes).length">
          <h3>Structured attributes</h3>
          <pre class="payload">{{ prettyAttributes }}</pre>
        </template>

        <template v-if="entry.raw && entry.raw !== entry.message">
          <h3>Original line</h3>
          <pre class="payload">{{ entry.raw }}</pre>
        </template>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import type { LogEntry } from '../api/client'
import { formatDateTime } from '../utils/format'
import AppIcon from './AppIcon.vue'
import SeverityBadge from './SeverityBadge.vue'

const props = defineProps<{ entry: LogEntry | null }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const copied = ref(false)
const prettyAttributes = computed(() => JSON.stringify(props.entry?.attributes ?? {}, null, 2))

function shortId(id: string): string {
  return id.length > 13 ? `${id.slice(0, 8)}…` : id
}

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

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.entry) emit('close')
}

onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>
