<!-- 步骤监护核查点编辑面板（spec §6 编写侧、D2/D3）。
     一个 step 节点可挂 0..N 个核查点；第一期类型只有 ocr/safety。
     自包含：直接调 checks API，增删后本地 re-GET。http 实例默认弹错误 toast，故此处不另处理。 -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import { createCheck, deleteCheck, listChecks, type NodeCheck } from '@/api/checks'

const props = withDefaults(defineProps<{ nodeId: string; readonly?: boolean }>(), {
  readonly: false,
})

const checks = ref<NodeCheck[]>([])
const loading = ref(false)
const adding = ref(false)
const saving = ref(false)

const draftType = ref<'ocr' | 'safety'>('ocr')
const ocrTarget = ref('')
const ocrMode = ref<'exact' | 'contains' | 'regex' | 'range'>('range')
const safetyItems = ref('gloves')
const prompt = ref('')

async function reload(): Promise<void> {
  loading.value = true
  try {
    checks.value = await listChecks(props.nodeId)
  } finally {
    loading.value = false
  }
}

watch(() => props.nodeId, reload, { immediate: true })

function resetDraft(): void {
  adding.value = false
  draftType.value = 'ocr'
  ocrTarget.value = ''
  ocrMode.value = 'range'
  safetyItems.value = 'gloves'
  prompt.value = ''
}

async function add(): Promise<void> {
  const params =
    draftType.value === 'ocr'
      ? { target_desc: ocrTarget.value, match_mode: ocrMode.value }
      : { items: safetyItems.value.split(',').map((s) => s.trim()).filter(Boolean) }
  saving.value = true
  try {
    await createCheck(props.nodeId, {
      check_type: draftType.value,
      modality: 'visual',
      severity: 'warn',
      trigger: 'on_enter',
      prompt: prompt.value,
      keep_evidence: true,
      confidence_threshold: null,
      params,
    })
    resetDraft()
    await reload()
  } finally {
    saving.value = false
  }
}

async function remove(id: string): Promise<void> {
  await deleteCheck(id)
  await reload()
}
</script>

<template>
  <div class="node-check-panel">
    <el-empty
      v-if="!loading && checks.length === 0 && !adding"
      description="暂无核查点"
      :image-size="48"
    />

    <ul v-if="checks.length" class="check-list">
      <li v-for="c in checks" :key="c.id">
        <el-tag size="small" :type="c.check_type === 'safety' ? 'danger' : 'warning'">
          {{ c.check_type }}
        </el-tag>
        <span class="prompt">{{ c.prompt || '(无提示语)' }}</span>
        <el-button v-if="!props.readonly" link type="danger" size="small" @click="remove(c.id)">
          删除
        </el-button>
      </li>
    </ul>

    <div v-if="adding" class="add-form">
      <el-select v-model="draftType" size="small" style="width: 120px">
        <el-option label="读数/OCR" value="ocr" />
        <el-option label="安全/合规" value="safety" />
      </el-select>

      <template v-if="draftType === 'ocr'">
        <el-input v-model="ocrTarget" size="small" placeholder="目标描述，如 压力表读数" />
        <el-select v-model="ocrMode" size="small" style="width: 120px">
          <el-option label="精确" value="exact" />
          <el-option label="包含" value="contains" />
          <el-option label="正则" value="regex" />
          <el-option label="数值范围" value="range" />
        </el-select>
      </template>
      <template v-else>
        <el-input v-model="safetyItems" size="small" placeholder="PPE 列表，逗号分隔，如 gloves,goggles" />
      </template>

      <el-input v-model="prompt" size="small" placeholder="操作者提示语" />
      <div class="form-actions">
        <el-button size="small" @click="resetDraft">取消</el-button>
        <el-button type="primary" size="small" :loading="saving" @click="add">保存</el-button>
      </div>
    </div>

    <el-button
      v-if="!props.readonly && !adding"
      class="add-btn"
      size="small"
      @click="adding = true"
    >
      + 添加核查点
    </el-button>
  </div>
</template>

<style scoped>
.node-check-panel { display: flex; flex-direction: column; gap: 8px; }
.check-list { list-style: none; padding: 0; margin: 0; }
.check-list li { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.check-list .prompt {
  flex: 1;
  min-width: 0;
  color: var(--text-secondary, #606266);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.add-form { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.form-actions { display: flex; gap: 8px; }
.add-btn { align-self: flex-start; }
</style>
