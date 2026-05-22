<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchFolderTree } from '@/api/folders'
import { createProcedure } from '@/api/procedures'
import type { FolderTreeNode } from '@/types/folder'
import type { LevelOfUse, ProcedureMeta } from '@/types/procedure'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'created', proc: ProcedureMeta): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

interface LeafOption {
  id: string
  label: string
  prefix: string
}
const leaves = ref<LeafOption[]>([])
const submitting = ref(false)

const LEVELS: { value: LevelOfUse; label: string }[] = [
  { value: 'reference', label: '参考 (reference)' },
  { value: 'continuous', label: '连续使用 (continuous)' },
  { value: 'information', label: '信息 (information)' },
]

interface FormState {
  folder_id: string
  name: string
  level_of_use: LevelOfUse
  description: string
  risk_level: number
  quality_level: number
}
const form = reactive<FormState>({
  folder_id: '',
  name: '',
  level_of_use: 'continuous',
  description: '',
  risk_level: 1,
  quality_level: 1,
})

function collectLeaves(nodes: FolderTreeNode[], acc: LeafOption[]): void {
  for (const n of nodes) {
    if (!n.system && n.children.length === 0 && n.prefix) {
      acc.push({ id: n.id, label: n.full_path, prefix: n.prefix })
    }
    if (n.children.length) collectLeaves(n.children, acc)
  }
}

async function loadLeaves(): Promise<void> {
  const tree = await fetchFolderTree()
  const acc: LeafOption[] = []
  collectLeaves(tree, acc)
  leaves.value = acc
}

watch(visible, (open) => {
  if (open) {
    Object.assign(form, {
      folder_id: '',
      name: '',
      level_of_use: 'continuous',
      description: '',
      risk_level: 1,
      quality_level: 1,
    })
    void loadLeaves()
  }
})

const codePreview = computed(() => {
  const leaf = leaves.value.find((l) => l.id === form.folder_id)
  return leaf ? `${leaf.prefix}-…（提交后自动生成）` : ''
})

async function submit(): Promise<void> {
  if (!form.folder_id) {
    ElMessage.warning('请选择目标叶子文件夹')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('请输入程序名称')
    return
  }
  submitting.value = true
  try {
    const proc = await createProcedure({
      folder_id: form.folder_id,
      name: form.name,
      level_of_use: form.level_of_use,
      description: form.description,
      risk_level: form.risk_level,
      quality_level: form.quality_level,
    })
    ElMessage.success(`已创建 ${proc.code}`)
    visible.value = false
    emit('created', proc)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="新建程序" width="520px">
    <el-form label-width="96px">
      <el-form-item label="目标文件夹" required>
        <el-select
          v-model="form.folder_id"
          filterable
          placeholder="仅可存程序的叶子文件夹"
          class="full"
        >
          <el-option v-for="leaf in leaves" :key="leaf.id" :label="leaf.label" :value="leaf.id" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="codePreview" label="编码预览">
        <span class="code-preview">{{ codePreview }}</span>
      </el-form-item>
      <el-form-item label="程序名称" required>
        <el-input v-model="form.name" maxlength="200" placeholder="程序名称" />
      </el-form-item>
      <el-form-item label="用途级别" required>
        <el-select v-model="form.level_of_use" class="full">
          <el-option v-for="lv in LEVELS" :key="lv.value" :label="lv.label" :value="lv.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="风险等级">
        <el-input-number v-model="form.risk_level" :min="1" :max="5" />
      </el-form-item>
      <el-form-item label="质量等级">
        <el-input-number v-model="form.quality_level" :min="1" :max="5" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="3" maxlength="10000" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">创建</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.full {
  width: 100%;
}
.code-preview {
  color: var(--accent);
  font-family: monospace;
}
</style>
