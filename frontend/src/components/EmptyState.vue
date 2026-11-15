<template>
  <div class="empty">
    <div class="empty-icon" :class="{ glow }">
      <AppIcon :name="icon" :size="25" />
    </div>
    <h3>{{ title }}</h3>
    <p>
      <slot>{{ hint }}</slot>
    </p>
    <div v-if="$slots.cta" class="empty-cta"><slot name="cta" /></div>
  </div>
</template>

<script setup lang="ts">
import AppIcon from './AppIcon.vue'

withDefaults(
  defineProps<{ title: string; hint?: string; icon?: string; glow?: boolean }>(),
  { hint: '', icon: 'inbox', glow: false },
)
</script>
