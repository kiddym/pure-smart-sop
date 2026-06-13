<!-- frontend/src/components/editor/ReferencePanel.vue -->
<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  listReferences,
  createReference,
  deleteReference,
  type ProcedureReference,
  type RelationType,
} from '@/api/references'
import { fetchProcedureList } from '@/api/procedures'

const props = withDefaults(
  defineProps<{ procedureId: string; sourceGroupId: string; readonly?: boolean }>(),
  { readonly: false },
)

const REL_LABELS: Record<RelationType, string> = {
  authoring_ref: '编写参考',
  exec_ref: '执行参考',
  upstream: '上游',
  downstream: '下游',
  related: '相关',
}

const refs = ref<ProcedureReference[]>([])
const loading = ref(false)
const adding = ref(false)
const saving = ref(false)

const draftType = ref<RelationType>('exec_ref')
const draftNote = ref('')
const draftTargetGroup = ref('')

// 目标 SOP 远程搜索：{ label, value=procedure_group_id }
const options = ref<{ label: string; value: string }[]>([])
const searching = ref(false)

async function reload(): Promise<void> {
  loading.value = true
  try {
    refs.value = await listReferences(props.procedureId)
  } finally {
    loading.value = false
  }
}

watch(() => props.procedureId, reload, { immediate: true })

async function remoteSearch(query: string): Promise<void> {
  if (!query) {
    options.value = []
    return
  }
  searching.value = true
  try {
    const page = await fetchProcedureList({ search: query, page: 1, page_size: 20 })
    options.value = page.items
      .filter((row) => row.procedure_group_id !== props.sourceGroupId) // 排除自身 SOP
      .map((row) => ({ label: `${row.code} ${row.name}`, value: row.procedure_group_id }))
  } finally {
    searching.value = false
  }
}

function resetDraft(): void {
  adding.value = false
  draftType.value = 'exec_ref'
  draftNote.value = ''
  draftTargetGroup.value = ''
  options.value = []
}

async function add(): Promise<void> {
  if (!draftTargetGroup.value) return
  saving.value = true
  try {
    await createReference(props.procedureId, {
      target_procedure_group_id: draftTargetGroup.value,
      relation_type: draftType.value,
      note: draftNote.value,
    })
    resetDraft()
    await reload()
  } finally {
    saving.value = false
  }
}

async function remove(id: string): Promise<void> {
  await deleteReference(id)
  await reload()
}
</script>

<template>
  <div class="reference-panel">
    <el-empty
      v-if="!loading && refs.length === 0 && !adding"
      description="暂无参考关系"
      :image-size="48"
    />

    <ul v-if="refs.length" class="ref-list">
      <li v-for="r in refs" :key="r.id">
        <el-tag size="small">{{ REL_LABELS[r.relation_type] }}</el-tag>
        <span class="target">{{ r.target_code ? `${r.target_code} ${r.target_name}` : '(目标无当前版本)' }}</span>
        <span class="note">{{ r.note }}</span>
        <el-button v-if="!props.readonly" link type="danger" size="small" @click="remove(r.id)">
          删除
        </el-button>
      </li>
    </ul>

    <div v-if="adding" class="add-form">
      <el-select v-model="draftType" size="small" style="width: 110px">
        <el-option v-for="(label, value) in REL_LABELS" :key="value" :label="label" :value="value" />
      </el-select>
      <el-select
        v-model="draftTargetGroup"
        size="small"
        filterable
        remote
        clearable
        :remote-method="remoteSearch"
        :loading="searching"
        placeholder="搜索目标 SOP（编号/名称）"
        style="width: 240px"
      >
        <el-option v-for="o in options" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-input v-model="draftNote" size="small" placeholder="说明（可选）" style="width: 200px" />
      <div class="form-actions">
        <el-button size="small" @click="resetDraft">取消</el-button>
        <el-button type="primary" size="small" :loading="saving" :disabled="!draftTargetGroup" @click="add">
          保存
        </el-button>
      </div>
    </div>

    <el-button
      v-if="!props.readonly && !adding"
      class="add-btn"
      size="small"
      @click="adding = true"
    >
      + 添加参考关系
    </el-button>
  </div>
</template>

<style scoped>
.reference-panel { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.ref-list { list-style: none; padding: 0; margin: 0; }
.ref-list li { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.ref-list .target { font-size: 13px; color: var(--text-primary, #303133); white-space: nowrap; }
.ref-list .note { flex: 1; min-width: 0; font-size: 12px; color: var(--text-secondary, #909399); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.add-form { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.form-actions { display: flex; gap: 8px; }
.add-btn { align-self: flex-start; }
</style>
