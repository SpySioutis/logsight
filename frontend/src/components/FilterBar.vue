<template>
  <div class="filterbar">
    <label class="field" style="min-width: 220px; flex: 1">
      Search
      <input
        type="search"
        :value="modelValue.q ?? ''"
        placeholder="message, source or service…"
        @input="update('q', ($event.target as HTMLInputElement).value || undefined)"
      />
    </label>

    <div class="field">
      <span style="font-size: 12px; color: var(--text-dim)">Severity</span>
      <div class="sev-toggles">
        <button
          v-for="sev in SEVERITIES"
          :key="sev"
          :class="['sev-toggle', { on: (modelValue.severity ?? []).includes(sev) }]"
          @click="toggleSeverity(sev)"
        >
          {{ sev }}
        </button>
      </div>
    </div>

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

    <button @click="$emit('clear')">Reset</button>
  </div>
</template>

<script setup lang="ts">
import type { LogQuery } from '../api/client'
import { SEVERITIES } from '../utils/severity'

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
</script>
