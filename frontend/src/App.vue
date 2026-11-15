<template>
  <div class="app-shell" :class="{ collapsed: settings.sidebarCollapsed, 'mobile-open': mobileOpen }">
    <div class="mobile-scrim" @click="mobileOpen = false"></div>

    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 15.5h3.2l1.8-5.8 2.8 7.6 2-5.2 1 2.2H21" />
          </svg>
        </span>
        <span class="brand-text brand-name">LogSight<small>Observability</small></span>
      </div>

      <div class="nav-scroll">
        <div v-for="group in navGroups" :key="group.label">
          <div class="nav-group-label">{{ group.label }}</div>
          <nav class="nav">
            <RouterLink
              v-for="item in group.items"
              :key="item.to"
              :to="item.to"
              :title="item.label"
              @click="mobileOpen = false"
            >
              <span class="nav-icon"><AppIcon :name="item.icon" :size="17" /></span>
              <span class="nav-label">{{ item.label }}</span>
            </RouterLink>
          </nav>
        </div>
      </div>

      <div class="side-foot">
        <span class="pulse-dot"></span>
        <span class="foot-text">self-hosted · local</span>
        <button
          class="ghost sm icon-only collapse-btn"
          :title="settings.sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'"
          @click="settings.toggleSidebar()"
        >
          <AppIcon name="chevrons-left" :size="15" />
        </button>
      </div>
    </aside>

    <div class="main-col">
      <header class="topbar">
        <button class="ghost sm icon-only hamburger" aria-label="Open navigation" @click="mobileOpen = true">
          <AppIcon name="menu" :size="18" />
        </button>
        <nav class="crumbs" aria-label="Breadcrumb">
          <span class="crumb-section">{{ route.meta.section ?? 'LogSight' }}</span>
          <span class="crumb-sep">/</span>
          <span class="crumb-page">{{ crumbTitle }}</span>
        </nav>
        <div class="topbar-actions">
          <button
            class="ghost sm icon-only"
            :title="settings.theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'"
            @click="toggleTheme"
          >
            <AppIcon :name="settings.theme === 'dark' ? 'sun' : 'moon'" :size="16" />
          </button>
          <RouterLink to="/imports" class="btn sm primary hide-mobile" style="text-decoration: none">
            <AppIcon name="plus" :size="14" /> Ingest logs
          </RouterLink>
          <RouterLink to="/imports" class="btn sm primary icon-only hamburger" style="text-decoration: none" aria-label="Ingest logs">
            <AppIcon name="plus" :size="15" />
          </RouterLink>
        </div>
      </header>

      <main class="main">
        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" :key="route.path" />
          </Transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { useSettingsStore } from './stores/settings'
import AppIcon from './components/AppIcon.vue'

const settings = useSettingsStore()
const route = useRoute()
const mobileOpen = ref(false)

interface NavItem {
  to: string
  label: string
  icon: string
}

const navGroups: { label: string; items: NavItem[] }[] = [
  { label: 'Overview', items: [{ to: '/', label: 'Dashboard', icon: 'dashboard' }] },
  {
    label: 'Observability',
    items: [
      { to: '/logs', label: 'Log Explorer', icon: 'logs' },
      { to: '/errors', label: 'Errors', icon: 'errors' },
      { to: '/traces', label: 'Traces', icon: 'traces' },
    ],
  },
  {
    label: 'Management',
    items: [
      { to: '/imports', label: 'Imports', icon: 'imports' },
      { to: '/filters', label: 'Saved Filters', icon: 'filters' },
    ],
  },
  {
    label: 'Preferences',
    items: [{ to: '/settings', label: 'Settings', icon: 'settings' }],
  },
]

const crumbTitle = computed(() => {
  if (route.name === 'trace') {
    const id = String(route.params.id ?? '')
    return `Trace ${id.length > 18 ? `${id.slice(0, 18)}…` : id}`
  }
  return route.meta.title ?? 'LogSight'
})

function toggleTheme() {
  settings.setTheme(settings.theme === 'dark' ? 'light' : 'dark')
}

onMounted(() => settings.applyTheme())
</script>
