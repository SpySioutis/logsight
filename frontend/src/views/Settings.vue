<template>
  <PageHeader title="Settings" subtitle="Appearance, defaults and backend status" />

  <div class="grid-2" style="align-items: start">
    <div style="display: flex; flex-direction: column; gap: 16px">
      <div class="panel rise" style="margin-top: 0">
        <h2><span class="h2-icon"><AppIcon name="sun" :size="15" /></span> Appearance</h2>
        <div class="settings-row">
          <div class="sr-main">
            <div class="sr-title">Theme</div>
            <div class="sr-desc">Dark-first by design; light mode is fully supported.</div>
          </div>
          <div class="segmented">
            <button :class="{ active: settings.theme === 'dark' }" @click="settings.setTheme('dark')">
              <AppIcon name="moon" :size="13" /> Dark
            </button>
            <button :class="{ active: settings.theme === 'light' }" @click="settings.setTheme('light')">
              <AppIcon name="sun" :size="13" /> Light
            </button>
          </div>
        </div>
        <div class="settings-row">
          <div class="sr-main">
            <div class="sr-title">Sidebar</div>
            <div class="sr-desc">Collapse the navigation into an icon rail.</div>
          </div>
          <label class="switch" title="Collapse sidebar">
            <input type="checkbox" :checked="settings.sidebarCollapsed" @change="settings.toggleSidebar()" />
            <span class="track"></span>
          </label>
        </div>
      </div>

      <div class="panel rise rise-1" style="margin-top: 0">
        <h2><span class="h2-icon"><AppIcon name="logs" :size="15" /></span> Explorer defaults</h2>
        <div class="settings-row">
          <div class="sr-main">
            <div class="sr-title">Rows per page</div>
            <div class="sr-desc">Default page size for the Log Explorer.</div>
          </div>
          <div class="segmented">
            <button :class="{ active: settings.pageSize === 25 }" @click="settings.setPageSize(25)">25</button>
            <button :class="{ active: settings.pageSize === 50 }" @click="settings.setPageSize(50)">50</button>
            <button :class="{ active: settings.pageSize === 100 }" @click="settings.setPageSize(100)">100</button>
          </div>
        </div>
      </div>
    </div>

    <div style="display: flex; flex-direction: column; gap: 16px">
      <div class="panel rise rise-1" style="margin-top: 0">
        <h2><span class="h2-icon"><AppIcon name="server" :size="15" /></span> Backend</h2>
        <dl class="kv" style="margin-top: 0">
          <dt>API base URL</dt>
          <dd class="mono" style="font-size: 12.5px">{{ apiBase }}</dd>
          <dt>Health</dt>
          <dd v-if="health" style="color: var(--success); font-weight: 600">
            <span class="import-status completed">reachable</span>
            <span class="dim mono" style="font-size: 12px; margin-left: 6px">{{ health.service }}</span>
          </dd>
          <dd v-else-if="healthChecked" style="color: var(--danger); font-weight: 600">
            <span class="import-status failed">unreachable</span>
          </dd>
          <dd v-else class="dim">checking…</dd>
          <dt>API docs</dt>
          <dd>
            <a :href="docsUrl" target="_blank" rel="noopener" style="display: inline-flex; align-items: center; gap: 5px">
              OpenAPI (Swagger UI) <AppIcon name="external" :size="13" />
            </a>
          </dd>
        </dl>
        <p class="dim" style="font-size: 12.5px; margin-bottom: 0">
          Upload limits and retention are configured server-side via
          <span class="mono">MAX_UPLOAD_MB</span>. See MANUAL.md for details.
        </p>
      </div>

      <div class="panel rise rise-2" style="margin-top: 0">
        <h2><span class="h2-icon"><AppIcon name="shield" :size="15" /></span> About</h2>
        <dl class="kv" style="margin-top: 0">
          <dt>Product</dt>
          <dd><strong>LogSight</strong> <span class="dim">· self-hosted log analysis</span></dd>
          <dt>Stack</dt>
          <dd class="mono" style="font-size: 12px">Vue 3 · FastAPI · PostgreSQL</dd>
          <dt>Grouping</dt>
          <dd class="dim" style="font-size: 12.5px">Deterministic message-shape fingerprints — no external AI calls.</dd>
        </dl>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api/client'
import { useSettingsStore } from '../stores/settings'
import AppIcon from '../components/AppIcon.vue'
import PageHeader from '../components/PageHeader.vue'

const settings = useSettingsStore()
const apiBase = import.meta.env.VITE_API_BASE_URL || `${window.location.origin}/api`
const docsUrl = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api/docs`
  : '/api/docs'
const health = ref<{ status: string; service: string } | null>(null)
const healthChecked = ref(false)

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
