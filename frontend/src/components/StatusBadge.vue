<template>
  <span :class="['status', status]">{{ status }}</span>
</template>

<script setup lang="ts">
defineProps<{ status: string }>()
</script>
