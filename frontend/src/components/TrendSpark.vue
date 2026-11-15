<template>
  <svg
    :width="width"
    :height="height"
    role="img"
    :aria-label="`Trend: ${max} peak over ${points.length} buckets`"
    class="spark"
  >
    <polyline :points="line" fill="none" stroke="currentColor" stroke-width="1.5" />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ErrorTrendPoint } from '../api/client'

const props = withDefaults(
  defineProps<{
    points: ErrorTrendPoint[]
    width?: number
    height?: number
  }>(),
  { width: 160, height: 36 },
)

const max = computed(() => Math.max(1, ...props.points.map((p) => p.count)))

const line = computed(() => {
  const n = props.points.length
  if (n === 0) return ''
  if (n === 1) return `0,${props.height - 2} ${props.width},${props.height - 2}`
  return props.points
    .map((p, i) => {
      const x = (i / (n - 1)) * (props.width - 2) + 1
      const y = props.height - 2 - (p.count / max.value) * (props.height - 6)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})
</script>

<style scoped>
.spark {
  display: block;
  color: var(--danger);
  opacity: 0.85;
}
</style>
