import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Explorer from '../views/Explorer.vue'
import Errors from '../views/Errors.vue'
import Imports from '../views/Imports.vue'
import SavedFilters from '../views/SavedFilters.vue'
import Settings from '../views/Settings.vue'
import TraceView from '../views/TraceView.vue'
import Traces from '../views/Traces.vue'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    section?: string
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard, meta: { title: 'Dashboard', section: 'Overview' } },
    { path: '/logs', name: 'logs', component: Explorer, meta: { title: 'Log Explorer', section: 'Observability' } },
    { path: '/errors', name: 'errors', component: Errors, meta: { title: 'Errors', section: 'Observability' } },
    { path: '/traces', name: 'traces', component: Traces, meta: { title: 'Traces', section: 'Observability' } },
    { path: '/imports', name: 'imports', component: Imports, meta: { title: 'Imports', section: 'Management' } },
    { path: '/filters', name: 'filters', component: SavedFilters, meta: { title: 'Saved Filters', section: 'Management' } },
    { path: '/settings', name: 'settings', component: Settings, meta: { title: 'Settings', section: 'Preferences' } },
    { path: '/traces/:id', name: 'trace', component: TraceView, meta: { title: 'Trace Detail', section: 'Observability' } },
  ],
})

export default router
