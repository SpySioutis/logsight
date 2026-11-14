<template>
  <div class="stat">
    <div class="label">{{ label }}</div>
    <div class="value" :class="tone">{{ formatted }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatNumber } from '../utils/format'

const props = withDefaults(defineProps<{ label: string; value: number; tone?: string }>(), { tone: '' })
const formatted = computed(() => formatNumber(props.value))
</script>
