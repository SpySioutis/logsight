<template>
  <div class="page-head">
    <div class="title-block">
      <h1><slot name="title">{{ title }}</slot></h1>
      <span v-if="subtitle || $slots.subtitle" class="sub">
        <slot name="subtitle">{{ subtitle }}</slot>
      </span>
    </div>
    <div class="head-actions"><slot name="actions" /></div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ title?: string; subtitle?: string }>(), { title: '', subtitle: '' })
</script>
