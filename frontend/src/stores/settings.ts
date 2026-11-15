import { defineStore } from 'pinia'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    theme: (localStorage.getItem('logsight-theme') as 'dark' | 'light') || 'dark',
    pageSize: Number(localStorage.getItem('logsight-page-size')) || 50,
    sidebarCollapsed: localStorage.getItem('logsight-sidebar') === 'collapsed',
  }),
  actions: {
    setTheme(theme: 'dark' | 'light') {
      this.theme = theme
      localStorage.setItem('logsight-theme', theme)
      document.documentElement.setAttribute('data-theme', theme)
    },
    setPageSize(size: number) {
      this.pageSize = size
      localStorage.setItem('logsight-page-size', String(size))
    },
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
      localStorage.setItem('logsight-sidebar', this.sidebarCollapsed ? 'collapsed' : 'open')
    },
    applyTheme() {
      document.documentElement.setAttribute('data-theme', this.theme)
    },
  },
})
