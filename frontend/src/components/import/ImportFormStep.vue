<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchFolderTree } from '@/api/folders'
import { collectLeafFolders, type LeafFolderOption } from '@/utils/folders'

// step5：导入表单（name 默认上传文件名 + folder_id 仅非系统叶子）。level_of_use 落库默认 reference（Q350）。
const props = defineProps<{ name: string; folderId: string }>()
const emit = defineEmits<{
  (e: 'update:name', v: string): void
  (e: 'update:folderId', v: string): void
}>()

const leaves = ref<LeafFolderOption[]>([])
const loading = ref(false)

const name = computed<string>({ get: () => props.name, set: (v) => emit('update:name', v) })
const folderId = computed<string>({ get: () => props.folderId, set: (v) => emit('update:folderId', v) })

const codePreview = computed(() => {
  const leaf = leaves.value.find((l) => l.id === folderId.value)
  return leaf ? `${leaf.prefix}-…（提交后自动生成）` : ''
})

onMounted(async () => {
  loading.value = true
  try {
    leaves.value = collectLeafFolders(await fetchFolderTree())
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading" class="form-step">
    <el-form label-width="110px">
      <el-form-item label="程序名称" required>
        <el-input v-model="name" maxlength="200" placeholder="程序名称（默认取文件名）" />
      </el-form-item>
      <el-form-item label="目标文件夹" required>
        <el-select v-model="folderId" filterable placeholder="仅可存程序的叶子文件夹" class="full">
          <el-option v-for="leaf in leaves" :key="leaf.id" :label="leaf.label" :value="leaf.id" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="codePreview" label="编码预览">
        <span class="code">{{ codePreview }}</span>
      </el-form-item>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="导入后用途级别默认为「参考」，可在程序详情中调整；图片将自动转为永久资源。"
      />
    </el-form>
  </div>
</template>

<style scoped>
.form-step {
  padding: 8px 0;
}
.full {
  width: 100%;
}
.code {
  color: var(--accent, #409eff);
  font-family: monospace;
}
</style>
