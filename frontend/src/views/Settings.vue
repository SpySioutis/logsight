<template>
  <div class="page-head">
    <h1>Settings</h1>
  </div>

  <div class="panel">
    <h2>Appearance</h2>
    <div class="toolbar">
      <label class="field" style="flex-direction: row; align-items: center">
        Theme
        <select :value="settings.theme" @change="onTheme">
          <option value="dark">Dark (default)</option>
          <option value="light">Light</option>
        </select>
      </label>
    </div>
  </div>

  <div class="panel">
    <h2>Explorer defaults</h2>
    <div class="toolbar">
      <label class="field" style="flex-direction: row; align-items: center">
        Rows per page
        <select :value="settings.pageSize" @change="onPageSize">
          <option :value="25">25</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
        </select>
      </label>
    </div>
  </div>

  <div class="panel">
    <h2>Backend</h2>
    <dl class="kv">
      <dt>API base URL</dt>
      <dd class="mono">{{ apiBase }}</dd>
      <dt>Health</dt>
      <dd v-if="health" style="color: var(--ok)">reachable · {{ health.service }}</dd>
      <dd v-else-if="healthChecked" style="color: var(--danger)">unreachable</dd>
      <dd v-else class="dim">checking…</dd>
      <dt>API docs</dt>
      <dd><a :href="docsUrl" target="_blank" rel="noopener">OpenAPI (Swagger UI)</a></dd>
    </dl>
    <p class="dim" style="font-size: 12.5px">
      Upload limits and retention are configured server-side via
      <span class="mono">MAX_UPLOAD_MB</span>. See MANUAL.md for details.
    </p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api/client'
import { useSettingsStore } from '../stores/settings'

const settings = useSettingsStore()
const apiBase = import.meta.env.VITE_API_BASE_URL || `${window.location.origin}/api`
const docsUrl = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api/docs`
  : '/api/docs'
const health = ref<{ status: string; service: string } | null>(null)
const healthChecked = ref(false)

function onTheme(event: Event) {
  settings.setTheme((event.target as HTMLSelectElement).value as 'dark' | 'light')
}

function onPageSize(event: Event) {
  settings.setPageSize(Number((event.target as HTMLSelectElement).value))
}

onMounted(async () => {
  settings.applyTheme()
  try {
    health.value = (await api.get('/health')).data
  } catch {
    health.value = null
  } finally {
    healthChecked.value = true
  }
})
</script>
