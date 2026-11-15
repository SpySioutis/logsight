<template>
  <svg
    :width="width"
    :height="height"
    role="img"
    :aria-label="`Trend: ${max} peak over ${points.length} buckets`"
    class="spark"
  >
    <defs>
      <linearGradient :id="fillId" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="currentColor" stop-opacity="0.35" />
        <stop offset="100%" stop-color="currentColor" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path :d="area" :fill="`url(#${fillId})`" />
    <path :d="line" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    <circle v-if="last" :cx="last.x" :cy="last.y" r="2.6" fill="currentColor" stroke="var(--bg-2)" stroke-width="1.2" />
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
  { width: 160, height: 40 },
)

const fillId = `spark-${Math.random().toString(36).slice(2, 8)}`
const max = computed(() => Math.max(1, ...props.points.map((p) => p.count)))

const coords = computed(() => {
  const n = props.points.length
  if (n === 0) return []
  if (n === 1) {
    const y = props.height - 4 - (props.points[0].count / max.value) * (props.height - 10)
    return [
      { x: 2, y },
      { x: props.width - 2, y },
    ]
  }
  return props.points.map((p, i) => ({
    x: (i / (n - 1)) * (props.width - 4) + 2,
    y: props.height - 4 - (p.count / max.value) * (props.height - 10),
  }))
})

function smooth(pts: { x: number; y: number }[]): string {
  if (pts.length < 2) return ''
  let d = `M ${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[Math.min(pts.length - 1, i + 2)]
    const c1x = p1.x + (p2.x - p0.x) / 6
    const c1y = p1.y + (p2.y - p0.y) / 6
    const c2x = p2.x - (p3.x - p1.x) / 6
    const c2y = p2.y - (p3.y - p1.y) / 6
    d += ` C ${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`
  }
  return d
}

const line = computed(() => smooth(coords.value))
const area = computed(() => {
  const l = line.value
  if (!l) return ''
  return `${l} L ${(props.width - 2).toFixed(1)},${props.height} L 2,${props.height} Z`
})
const last = computed(() => (coords.value.length ? coords.value[coords.value.length - 1] : null))
</script>

<style scoped>
.spark {
  display: block;
  color: var(--danger);
}
</style>
