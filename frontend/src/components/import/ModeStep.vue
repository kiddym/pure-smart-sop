<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchParseMethods } from '@/api/parse'
import type { ParseMethod, ParseMode } from '@/types/parse'

// step2：解析模式选择（默认 smart）。label/description 取自 GET /parse/methods。
const props = defineProps<{ modelValue: ParseMode }>()
const emit = defineEmits<{ (e: 'update:modelValue', value: ParseMode): void }>()

const methods = ref<ParseMethod[]>([])
const loading = ref(false)

const mode = computed<ParseMode>({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

onMounted(async () => {
  loading.value = true
  try {
    methods.value = await fetchParseMethods()
  } catch {
    /* 拦截器已提示；保留空列表回退到内置文案 */
  } finally {
    loading.value = false
  }
})

const FALLBACK: ParseMethod[] = [
  { key: 'standard', label: '标准模式', description: '仅依赖 Word 标题样式，模板规范文档识别最准。' },
  { key: 'smart', label: '智能模式', description: '样式 + 启发式置信度分级，低置信项标 review 待确认。' },
]
const list = computed(() => (methods.value.length ? methods.value : FALLBACK))
</script>

<template>
  <div v-loading="loading" class="mode-step">
    <el-radio-group v-model="mode" class="group">
      <el-card
        v-for="m in list"
        :key="m.key"
        shadow="hover"
        class="card"
        :class="{ active: mode === m.key }"
        @click="mode = m.key as ParseMode"
      >
        <el-radio :value="m.key" class="radio">
          <span class="label">{{ m.label }}</span>
        </el-radio>
        <div class="desc">{{ m.description }}</div>
      </el-card>
    </el-radio-group>
  </div>
</template>

<style scoped>
.mode-step {
  padding: 8px 0;
}
.group {
  display: flex;
  gap: 16px;
  width: 100%;
}
.card {
  flex: 1;
  cursor: pointer;
}
.card.active {
  border-color: var(--el-color-primary, #409eff);
}
.radio {
  height: auto;
}
.label {
  font-weight: 600;
  font-size: 15px;
}
.desc {
  margin-top: 8px;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}
</style>
