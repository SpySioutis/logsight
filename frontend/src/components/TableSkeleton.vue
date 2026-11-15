<template>
  <div aria-hidden="true">
    <div v-for="n in rows" :key="n" class="skel-row">
      <div class="skeleton" style="width: 130px"></div>
      <div class="skeleton" style="width: 70px"></div>
      <div class="skeleton" style="flex: 1"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ rows?: number }>(), { rows: 6 })
</script>
