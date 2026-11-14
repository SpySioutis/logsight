<template>
  <span :class="['sev', `sev-${severity}`]">{{ severity }}</span>
</template>

<script setup lang="ts">
defineProps<{ severity: string }>()
</script>
