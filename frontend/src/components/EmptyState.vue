<template>
  <div class="empty">
    <h3>{{ title }}</h3>
    <p><slot>{{ hint }}</slot></p>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ title: string; hint?: string }>(), { hint: '' })
</script>
