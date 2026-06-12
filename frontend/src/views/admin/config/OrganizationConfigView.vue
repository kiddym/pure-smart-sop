<script setup lang="ts">
import SettingsView from '@/views/settings/SettingsView.vue'
</script>

<template>
  <div class="config-aggregate">
    <h2 class="page-title">系统设置</h2>
    <SettingsView />
  </div>
</template>

<style scoped>
.config-aggregate {
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 12px;
  color: var(--text-primary);
}
</style>
