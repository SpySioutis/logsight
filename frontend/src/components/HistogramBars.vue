<template>
  <div class="histo" :class="{ busy: loading }">
    <svg
      :viewBox="`0 0 ${width} ${height}`"
      preserveAspectRatio="none"
      class="histo-svg"
      role="img"
      :aria-label="`Matching entries per ${bucket}`"
      @mouseleave="hovered = null"
    >
      <line :x1="0" :x2="width" :y1="height - 0.5" :y2="height - 0.5" class="axis" />
      <g v-for="(p, i) in points" :key="p.bucket">
        <rect
          :x="i * slot"
          :y="0"
          :width="slot"
          :height="height"
          class="hit"
          @mouseenter="hovered = i"
          @click="$emit('zoom', p.bucket)"
        />
        <rect :x="i * slot + gap / 2" :y="height - barH(p.total)" :width="barW" :height="barH(p.total)" class="bar" :class="{ on: hovered === i }" />
        <rect
          v-if="p.errors"
          :x="i * slot + gap / 2"
          :y="height - barH(p.errors)"
          :width="barW"
          :height="barH(p.errors)"
          class="bar err"
        />
      </g>
    </svg>
    <div class="histo-foot">
      <span class="mono">{{ points.length ? formatBucket(points[0].bucket) : '' }}</span>
      <span v-if="hovered !== null" class="histo-tip">
        <span class="mono">{{ formatBucket(points[hovered].bucket) }}</span>
        · {{ formatNumber(points[hovered].total) }} entries
        <template v-if="points[hovered].errors">· <span class="err-text">{{ formatNumber(points[hovered].errors) }} errors</span></template>
        <span class="faint">— click to zoom</span>
      </span>
      <span v-else class="faint">per {{ bucket }} · click a bar to zoom in</span>
      <span class="mono">{{ points.length ? formatBucket(points[points.length - 1].bucket) : '' }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { TimelinePoint } from '../api/client'
import { formatNumber } from '../utils/format'

const props = defineProps<{ points: TimelinePoint[]; bucket: string; loading?: boolean }>()
defineEmits<{ (e: 'zoom', bucket: string): void }>()

const width = 1000
const height = 64
const hovered = ref<number | null>(null)

const slot = computed(() => width / Math.max(1, props.points.length))
const gap = computed(() => (slot.value > 6 ? Math.min(4, slot.value * 0.2) : 0))
const barW = computed(() => Math.max(0.5, slot.value - gap.value))
const max = computed(() => Math.max(1, ...props.points.map((p) => p.total)))

function barH(value: number): number {
  // Non-zero buckets always get at least 2px so rare events stay visible.
  return value > 0 ? Math.max(2, (value / max.value) * (height - 2)) : 0
}

function formatBucket(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const opts: Intl.DateTimeFormatOptions =
    props.bucket === 'month'
      ? { year: 'numeric', month: 'short' }
      : props.bucket === 'day'
        ? { year: 'numeric', month: 'short', day: '2-digit' }
        : { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }
  return d.toLocaleString('en-GB', opts)
}
</script>

<style scoped>
.histo { margin: 4px 0 12px; }
.histo.busy { opacity: 0.55; }
.histo-svg { width: 100%; height: 64px; display: block; }
.axis { stroke: var(--border-soft); stroke-width: 1; }
.hit { fill: transparent; cursor: zoom-in; }
.bar { fill: var(--accent); opacity: 0.55; pointer-events: none; }
.bar.on { opacity: 0.9; }
.bar.err { fill: var(--danger); opacity: 0.85; }
.histo-foot {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 11px;
  color: var(--text-3);
  margin-top: 4px;
}
.histo-tip { color: var(--text-2); }
.err-text { color: var(--danger); }
</style>
