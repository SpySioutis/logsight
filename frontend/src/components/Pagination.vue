<template>
  <div class="pager">
    <button :disabled="page <= 1" @click="$emit('change', page - 1)">← Prev</button>
    <span>Page {{ page }} of {{ pages }} · {{ formattedTotal }} rows</span>
    <button :disabled="page >= pages" @click="$emit('change', page + 1)">Next →</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatNumber } from '../utils/format'

const props = defineProps<{ page: number; pages: number; total: number }>()
defineEmits<{ (e: 'change', page: number): void }>()
const formattedTotal = computed(() => formatNumber(props.total))
</script>
