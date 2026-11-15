<template>
  <div class="stat" :class="toneClass">
    <div class="stat-top">
      <span v-if="icon" class="stat-icon"><AppIcon :name="icon" :size="16" /></span>
      <span class="label">{{ label }}</span>
    </div>
    <div class="value" :class="legacyTone">{{ formatted }}</div>
    <div v-if="sub" class="sub-line">{{ sub }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatNumber } from '../utils/format'
import AppIcon from './AppIcon.vue'

const props = withDefaults(
  defineProps<{
    label: string
    value: number
    tone?: string
    icon?: string
    sub?: string
  }>(),
  { tone: '', icon: '', sub: '' },
)

const formatted = computed(() => formatNumber(props.value))

/** Map legacy tone names (danger/warn/ok) to card accent classes. */
const toneClass = computed(() => {
  switch (props.tone) {
    case 'danger':
      return 'tone-danger'
    case 'warn':
      return 'tone-warn'
    case 'ok':
      return 'tone-ok'
    case 'info':
      return 'tone-info'
    case 'violet':
      return 'tone-violet'
    default:
      return props.tone ? `tone-${props.tone}` : ''
  }
})

const legacyTone = computed(() =>
  props.tone === 'danger' || props.tone === 'warn' || props.tone === 'ok' ? props.tone : '',
)
</script>
