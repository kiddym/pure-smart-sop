<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ParseWarning } from '@/types/parse'

const props = defineProps<{ notes: ParseWarning[] }>()
const expanded = ref(false)
const total = computed(() => props.notes.length)
const blocking = computed(() => props.notes.filter((n) => n.severity === 'blocking'))
const info = computed(() => props.notes.filter((n) => n.severity !== 'blocking'))
</script>

<template>
  <div v-if="total" class="parse-notice">
    <button class="pn-head" type="button" @click="expanded = !expanded">
      <span class="pn-icon">ⓘ</span>
      解析提示 {{ total }} 条
      <span class="pn-toggle">{{ expanded ? '收起' : '展开' }}</span>
    </button>
    <ul v-show="expanded" class="pn-list">
      <li v-for="(w, i) in blocking" :key="'b' + i" class="pn-blocking">
        已知缺失（已放行）：{{ w.message }}
      </li>
      <li v-for="(w, i) in info" :key="'i' + i" class="pn-info">{{ w.message }}</li>
    </ul>
  </div>
</template>

<style scoped>
.parse-notice { border: 1px solid #f5dab1; background: #fdf6ec; border-radius: 4px; margin: 0 0 8px; }
.pn-head { display: flex; align-items: center; gap: 6px; width: 100%; border: 0; background: none;
  padding: 6px 10px; font-size: 12px; color: #b88230; cursor: pointer; }
.pn-toggle { margin-left: auto; color: #909399; }
.pn-list { margin: 0; padding: 0 12px 8px 28px; font-size: 12px; }
.pn-list li { margin: 2px 0; }
.pn-blocking { color: var(--el-color-danger, #f56c6c); }
.pn-info { color: #606266; }
</style>
