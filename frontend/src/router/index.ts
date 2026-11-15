import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Explorer from '../views/Explorer.vue'
import Errors from '../views/Errors.vue'
import Imports from '../views/Imports.vue'
import SavedFilters from '../views/SavedFilters.vue'
import Settings from '../views/Settings.vue'
import TraceView from '../views/TraceView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/logs', name: 'logs', component: Explorer },
    { path: '/errors', name: 'errors', component: Errors },
    { path: '/imports', name: 'imports', component: Imports },
    { path: '/filters', name: 'filters', component: SavedFilters },
    { path: '/settings', name: 'settings', component: Settings },
    { path: '/traces/:id', name: 'trace', component: TraceView },
  ],
})

export default router
