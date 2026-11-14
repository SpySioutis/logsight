<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">Log<span>Sight</span></div>
      <nav class="nav">
        <RouterLink to="/">Dashboard</RouterLink>
        <RouterLink to="/logs">Log Explorer</RouterLink>
        <RouterLink to="/errors">Error Analysis</RouterLink>
        <RouterLink to="/imports">Sources / Imports</RouterLink>
        <RouterLink to="/filters">Saved Filters</RouterLink>
        <RouterLink to="/settings">Settings</RouterLink>
      </nav>
      <div class="side-foot">self-hosted log analysis</div>
    </aside>
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>
