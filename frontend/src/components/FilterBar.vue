<template>
  <div class="filterbar">
    <div class="search-hero">
      <AppIcon name="search" class="search-glyph" :size="16" />
      <input
        ref="searchInput"
        type="search"
        :value="modelValue.q ?? ''"
        placeholder='Search logs — words, "exact phrase", -exclude, service:api…'
        title='Operators: "exact phrase", -exclude, service:x, source:x, severity:error, trace:id, request:id'
        @input="update('q', ($event.target as HTMLInputElement).value || undefined)"
        @keydown.escape="blurSearch"
      />
      <span class="kbd-hint"><kbd>/</kbd></span>
    </div>

    <div class="field" style="min-width: 0">
      <span style="font-size: 12px; color: var(--text-2); font-weight: 550">Severity</span>
      <div class="sev-toggles">
        <button
          v-for="sev in SEVERITIES"
          :key="sev"
          :data-sev="sev"
          :class="['sev-toggle', { on: (modelValue.severity ?? []).includes(sev) }]"
          :title="`Toggle ${sev}`"
          @click="toggleSeverity(sev)"
        >
          {{ sev }}
        </button>
      </div>
    </div>

    <button class="ghost sm" style="align-self: flex-end" @click="showAdvanced = !showAdvanced">
      <AppIcon name="funnel" :size="14" />
      {{ showAdvanced ? 'Hide filters' : 'More filters' }}
      <AppIcon :name="showAdvanced ? 'chevron-down' : 'chevron-right'" :size="13" />
    </button>
    <button class="ghost sm" style="align-self: flex-end" @click="$emit('clear')">
      <AppIcon name="x" :size="14" /> Reset
    </button>

    <div v-if="showAdvanced || hasAdvanced" class="filterbar-advanced">
      <label class="field">
        Source
        <input
          type="text"
          list="source-options"
          :value="modelValue.source ?? ''"
          placeholder="contains…"
          @input="update('source', ($event.target as HTMLInputElement).value || undefined)"
        />
        <datalist id="source-options">
          <option v-for="s in sources" :key="s" :value="s" />
        </datalist>
      </label>

      <label class="field">
        Service
        <input
          type="text"
          list="service-options"
          :value="modelValue.service ?? ''"
          placeholder="contains…"
          @input="update('service', ($event.target as HTMLInputElement).value || undefined)"
        />
        <datalist id="service-options">
          <option v-for="s in services" :key="s" :value="s" />
        </datalist>
      </label>

      <label class="field">
        Trace ID
        <input
          type="text"
          :value="modelValue.trace_id ?? ''"
          placeholder="exact…"
          @input="update('trace_id', ($event.target as HTMLInputElement).value || undefined)"
        />
      </label>

      <label class="field">
        Request ID
        <input
          type="text"
          :value="modelValue.request_id ?? ''"
          placeholder="exact…"
          @input="update('request_id', ($event.target as HTMLInputElement).value || undefined)"
        />
      </label>

      <label class="field">
        From
        <input
          type="datetime-local"
          :value="modelValue.date_from ?? ''"
          @input="update('date_from', ($event.target as HTMLInputElement).value || undefined)"
        />
      </label>

      <label class="field">
        To
        <input
          type="datetime-local"
          :value="modelValue.date_to ?? ''"
          @input="update('date_to', ($event.target as HTMLInputElement).value || undefined)"
        />
      </label>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { LogQuery } from '../api/client'
import { SEVERITIES } from '../utils/severity'
import AppIcon from './AppIcon.vue'

const props = withDefaults(
  defineProps<{
    modelValue: LogQuery
    sources?: string[]
    services?: string[]
  }>(),
  { sources: () => [], services: () => [] },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: LogQuery): void
  (e: 'clear'): void
}>()

const showAdvanced = ref(false)
const searchInput = ref<HTMLInputElement | null>(null)

const hasAdvanced = computed(
  () =>
    !!(
      props.modelValue.source ||
      props.modelValue.service ||
      props.modelValue.trace_id ||
      props.modelValue.request_id ||
      props.modelValue.date_from ||
      props.modelValue.date_to
    ),
)

function update<K extends keyof LogQuery>(key: K, value: LogQuery[K]) {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}

function toggleSeverity(sev: string) {
  const current = new Set(props.modelValue.severity ?? [])
  if (current.has(sev)) {
    current.delete(sev)
  } else {
    current.add(sev)
  }
  emit('update:modelValue', { ...props.modelValue, severity: [...current] })
}

function blurSearch() {
  searchInput.value?.blur()
}

function onKeydown(e: KeyboardEvent) {
  const target = e.target as HTMLElement
  const typing = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT'
  if (e.key === '/' && !typing) {
    e.preventDefault()
    searchInput.value?.focus()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>
