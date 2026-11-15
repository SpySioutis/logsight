<template>
  <div class="pager">
    <button class="sm icon-only" :disabled="page <= 1" aria-label="First page" @click="$emit('change', 1)">
      <AppIcon name="chevrons-left" :size="14" />
    </button>
    <button class="sm" :disabled="page <= 1" @click="$emit('change', page - 1)">
      <AppIcon name="chevron-left" :size="14" /> Prev
    </button>
    <span class="page-nums">
      <button
        v-for="p in visiblePages"
        :key="p"
        class="sm"
        :class="{ active: p === page }"
        @click="$emit('change', p)"
      >
        {{ p }}
      </button>
    </span>
    <button class="sm" :disabled="page >= pages" @click="$emit('change', page + 1)">
      Next <AppIcon name="chevron-right" :size="14" />
    </button>
    <button class="sm icon-only" :disabled="page >= pages" aria-label="Last page" @click="$emit('change', pages)">
      <AppIcon name="chevrons-right" :size="14" />
    </button>
    <span class="faint" style="margin-left: 6px">{{ formattedTotal }} rows · page {{ page }} of {{ pages }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatNumber } from '../utils/format'
import AppIcon from './AppIcon.vue'

const props = defineProps<{ page: number; pages: number; total: number }>()
defineEmits<{ (e: 'change', page: number): void }>()

const formattedTotal = computed(() => formatNumber(props.total))

/** Sliding window of up to 5 page numbers around the current page. */
const visiblePages = computed(() => {
  const total = Math.max(1, props.pages)
  const current = Math.min(Math.max(1, props.page), total)
  let start = Math.max(1, Math.min(current - 2, total - 4))
  const end = Math.min(total, start + 4)
  start = Math.max(1, end - 4)
  const out: number[] = []
  for (let p = start; p <= end; p++) out.push(p)
  return out
})
</script>
