<template>
  <div class="chart-shell" style="position: relative">
    <svg
      :viewBox="`0 0 ${width} ${height}`"
      class="chart chart-area"
      role="img"
      :aria-label="label"
      @mousemove="onHover"
      @mouseleave="hovered = null"
    >
      <defs>
        <linearGradient :id="totalFillId" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#8b5cf6" stop-opacity="0.42" />
          <stop offset="100%" stop-color="#8b5cf6" stop-opacity="0.02" />
        </linearGradient>
        <linearGradient :id="errorFillId" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#fb7185" stop-opacity="0.4" />
          <stop offset="100%" stop-color="#fb7185" stop-opacity="0.02" />
        </linearGradient>
        <linearGradient :id="totalLineId" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#8b5cf6" />
          <stop offset="100%" stop-color="#22d3ee" />
        </linearGradient>
      </defs>

      <text
        v-for="tick in yTicks"
        :key="tick"
        :x="padL - 8"
        :y="y(tick) + 3.5"
        class="y-label"
        text-anchor="end"
      >{{ formatTick(tick) }}</text>
      <line
        v-for="tick in yTicks"
        :key="`g-${tick}`"
        :x1="padL"
        :x2="width - padR"
        :y1="y(tick)"
        :y2="y(tick)"
        class="grid-line"
      />

      <path :d="totalArea" :fill="`url(#${totalFillId})`" />
      <path v-if="showErrors" :d="errorArea" :fill="`url(#${errorFillId})`" />
      <path :d="totalLine" fill="none" :stroke="`url(#${totalLineId})`" stroke-width="2.4" stroke-linecap="round" class="chart-line-draw" />
      <path v-if="showErrors" :d="errorLine" fill="none" stroke="#fb7185" stroke-width="1.8" stroke-linecap="round" opacity="0.9" />

      <g v-if="hovered !== null">
        <line :x1="xPos(hovered)" :x2="xPos(hovered)" :y1="padTop" :y2="height - padBottom" class="hover-line" />
        <circle :cx="xPos(hovered)" :cy="y(points[hovered].total)" r="4.4" fill="#fff" :stroke="`url(#${totalLineId})`" stroke-width="2.5" />
      </g>

      <text
        v-for="(item, i) in xLabels"
        :key="`x-${i}`"
        :x="item.x"
        :y="height - 6"
        class="x-label"
        :text-anchor="item.anchor"
      >{{ item.text }}</text>
    </svg>
    <div v-if="hovered !== null" class="chart-tooltip" :style="tooltipStyle">
      <div style="color: var(--text-2); font-size: 11px">{{ points[hovered].xLabel ?? points[hovered].key }}</div>
      <div><span class="tt-total">{{ formatNumber(points[hovered].total) }}</span> total</div>
      <div v-if="showErrors"><span class="tt-errors">{{ formatNumber(points[hovered].errors ?? 0) }}</span> errors</div>
    </div>
  </div>
  <div v-if="showErrors" class="legend">
    <span class="swatch total"></span> total
    <span class="swatch errors"></span> errors
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { formatNumber } from '../utils/format'

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

const width = 680
const height = 220
const padL = 46
const padR = 14
const padTop = 14
const padBottom = 28

const uid = Math.random().toString(36).slice(2, 8)
const totalFillId = `ls-total-${uid}`
const errorFillId = `ls-err-${uid}`
const totalLineId = `ls-line-${uid}`

const hovered = ref<number | null>(null)

const maxValue = computed(() => Math.max(1, ...props.points.map((p) => p.total)))
const base = computed(() => height - padBottom)

const y = (value: number) =>
  padTop + (height - padTop - padBottom) * (1 - value / maxValue.value)

function xPos(i: number): number {
  const n = Math.max(1, props.points.length)
  if (n === 1) return padL + (width - padL - padR) / 2
  return padL + (i / (n - 1)) * (width - padL - padR)
}

function smoothPath(values: number[]): string {
  const pts = values.map((v, i) => ({ x: xPos(i), y: y(v) }))
  if (pts.length === 1) return `M ${pts[0].x - 24},${pts[0].y} L ${pts[0].x + 24},${pts[0].y}`
  // Clamp control points vertically so steep spikes never overshoot below zero.
  const clampY = (v: number) => Math.min(base.value, Math.max(padTop, v))
  let d = `M ${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[Math.min(pts.length - 1, i + 2)]
    const c1x = p1.x + (p2.x - p0.x) / 6
    const c1y = clampY(p1.y + (p2.y - p0.y) / 6)
    const c2x = p2.x - (p3.x - p1.x) / 6
    const c2y = clampY(p2.y - (p3.y - p1.y) / 6)
    d += ` C ${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`
  }
  return d
}

const totals = computed(() => props.points.map((p) => p.total))
const errorVals = computed(() => props.points.map((p) => Math.min(p.errors ?? 0, p.total)))

const totalLine = computed(() => smoothPath(totals.value))
const errorLine = computed(() => smoothPath(errorVals.value))
const totalArea = computed(() => {
  const n = props.points.length
  if (!n) return ''
  return `${totalLine.value} L ${xPos(n - 1).toFixed(1)},${base.value} L ${xPos(0).toFixed(1)},${base.value} Z`
})
const errorArea = computed(() => {
  const n = props.points.length
  if (!n) return ''
  return `${errorLine.value} L ${xPos(n - 1).toFixed(1)},${base.value} L ${xPos(0).toFixed(1)},${base.value} Z`
})

const yTicks = computed(() => {
  const max = maxValue.value
  const step = Math.max(1, Math.ceil(max / 4))
  const ticks: number[] = []
  for (let v = 0; v <= max; v += step) ticks.push(v)
  return ticks
})

const xLabels = computed(() => {
  const n = props.points.length
  if (!n) return []
  const count = Math.min(6, n)
  const picks = new Set<number>()
  for (let k = 0; k < count; k++) picks.add(Math.round((k / Math.max(1, count - 1)) * (n - 1)))
  const sorted = [...picks].sort((a, b) => a - b)
  return sorted.map((i) => ({
    x: i === 0 ? padL : i === n - 1 ? width - padR : xPos(i),
    text: props.points[i].xLabel ?? props.points[i].key,
    anchor: i === 0 ? 'start' : i === n - 1 ? 'end' : 'middle',
  }))
})

function formatTick(v: number): string {
  if (v >= 1000) return `${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k`
  return String(v)
}

function onHover(event: MouseEvent) {
  const svg = event.currentTarget as SVGSVGElement
  const rect = svg.getBoundingClientRect()
  const px = ((event.clientX - rect.left) / rect.width) * width
  const n = props.points.length
  if (!n) return
  let best = 0
  let bestDist = Infinity
  for (let i = 0; i < n; i++) {
    const d = Math.abs(xPos(i) - px)
    if (d < bestDist) {
      bestDist = d
      best = i
    }
  }
  hovered.value = best
}

const tooltipStyle = computed(() => {
  if (hovered.value === null) return {}
  const frac = xPos(hovered.value) / width
  const left = Math.min(0.82, Math.max(0.08, frac)) * 100
  return { left: `${left}%`, top: '0', transform: 'translate(-50%, -4px)' }
})
</script>

<style scoped>
.chart { width: 100%; height: auto; display: block; }
.chart-shell { overflow: visible; }
.grid-line { stroke: var(--border-soft); stroke-width: 1; }
.y-label { fill: var(--text-3); font-size: 10px; font-family: var(--mono); }
.x-label { fill: var(--text-3); font-size: 10.5px; font-family: var(--mono); }
.hover-line { stroke: var(--border-strong); stroke-width: 1; stroke-dasharray: 4 3; }
</style>
