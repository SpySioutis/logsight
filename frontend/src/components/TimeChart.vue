<template>
  <svg :viewBox="`0 0 ${width} ${height}`" class="chart" role="img" :aria-label="label">
    <line
      v-for="tick in yTicks"
      :key="tick"
      :x1="padL"
      :x2="width - padR"
      :y1="y(tick)"
      :y2="y(tick)"
      class="grid-line"
    />
    <rect
      v-for="(bar, i) in bars"
      :key="i"
      :x="bar.x"
      :y="bar.y"
      :width="bar.w"
      :height="bar.h"
      class="bar"
    >
      <title>{{ bar.title }}</title>
    </rect>
    <g v-if="showErrors">
      <rect
        v-for="(bar, i) in bars"
        :key="`e-${i}`"
        :x="bar.x"
        :y="bar.ey"
        :width="bar.w"
        :height="bar.eh"
        class="bar-errors"
      >
        <title>{{ bar.title }}</title>
      </rect>
    </g>
    <text
      v-for="(bar, i) in xLabels"
      :key="`x-${i}`"
      :x="bar.x"
      :y="height - 4"
      class="x-label"
    >{{ bar.text }}</text>
  </svg>
  <div v-if="showErrors" class="legend">
    <span class="swatch total"></span> total
    <span class="swatch errors"></span> errors
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Point {
  key: string
  total: number
  errors?: number
  xLabel?: string
}

const props = withDefaults(
  defineProps<{ points: Point[]; label: string; showErrors?: boolean }>(),
  { showErrors: false },
)

const width = 640
const height = 180
const padL = 8
const padR = 8
const padTop = 8
const padBottom = 20

const maxValue = computed(() => Math.max(1, ...props.points.map((p) => p.total)))

const y = (value: number) =>
  padTop + (height - padTop - padBottom) * (1 - value / maxValue.value)

const yTicks = computed(() => {
  const max = maxValue.value
  const step = Math.max(1, Math.ceil(max / 4))
  const ticks: number[] = []
  for (let v = 0; v <= max; v += step) ticks.push(v)
  return ticks
})

const bars = computed(() => {
  const n = Math.max(1, props.points.length)
  const slot = (width - padL - padR) / n
  const w = Math.max(2, Math.min(28, slot * 0.62))
  return props.points.map((p, i) => {
    const x = padL + slot * i + (slot - w) / 2
    const h = Math.max(p.total > 0 ? 2 : 0, ((height - padTop - padBottom) * p.total) / maxValue.value)
    const errors = p.errors ?? 0
    const eh = (h * Math.min(errors, p.total)) / Math.max(1, p.total)
    return {
      x,
      y: y(p.total),
      w,
      h,
      ey: y(p.total) + h - eh,
      eh,
      title: `${p.key}: ${p.total} total${props.showErrors ? `, ${errors} errors` : ''}`,
    }
  })
})

const xLabels = computed(() => {
  const idx = new Set<number>()
  const n = bars.value.length
  for (let i = 0; i < n; i += Math.ceil(n / 6)) idx.add(i)
  return [...idx].map((i) => ({
    x: bars.value[i].x,
    text: props.points[i].xLabel ?? props.points[i].key,
  }))
})
</script>

<style scoped>
.chart { width: 100%; height: auto; display: block; }
.grid-line { stroke: var(--border-soft); stroke-width: 1; }
.bar { fill: var(--accent); opacity: 0.75; }
.bar-errors { fill: var(--danger); opacity: 0.9; }
.x-label { fill: var(--text-faint); font-size: 10px; }
.legend { display: flex; gap: 6px; align-items: center; font-size: 12px; color: var(--text-dim); margin-top: 6px; }
.swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.swatch.total { background: var(--accent); }
.swatch.errors { background: var(--danger); margin-left: 10px; }
</style>
