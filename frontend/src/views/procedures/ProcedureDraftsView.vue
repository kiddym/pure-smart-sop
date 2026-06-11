<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import ProcedureTable from '@/components/ProcedureTable.vue'
import CreateProcedureDialog from '@/components/CreateProcedureDialog.vue'
import CreateFromWordDialog from '@/components/CreateFromWordDialog.vue'
import { fetchProcedureList } from '@/api/procedures'
import type { ProcedureMeta, ProcedureRow } from '@/types/procedure'

const router = useRouter()
const rows = ref<ProcedureRow[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)

const createVisible = ref(false)
const wordVisible = ref(false)

// 「新建」入口与程序库一致：空白程序 / 从 Word 导入。批量导入需先选目标文件夹，
// 草稿箱无文件夹上下文，故引导用户去程序库操作。
function onCreateCommand(c: string): void {
  if (c === 'word') {
    wordVisible.value = true
  } else if (c === 'batch') {
    ElMessage.info('批量导入请在「程序库」中选择目标文件夹后操作')
    void router.push('/procedures/library')
  } else {
    createVisible.value = true
  }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const res = await fetchProcedureList({
      page: page.value,
      page_size: pageSize.value,
      status: 'DRAFT',
      sort: '-updated_at',
    })
    rows.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

onMounted(load)

function onPage(p: number): void {
  page.value = p
  void load()
}

function open(id: string): void {
  void router.push(`/procedures/${id}`)
}

function onCreated(proc: ProcedureMeta): void {
  void router.push(`/procedures/${proc.id}/edit`)
}

function onImported(id: string): void {
  void router.push({ path: `/procedures/${id}/edit`, query: { from: 'import' } })
}
</script>

<template>
  <div class="drafts">
    <div class="toolbar">
      <h2 class="title">草稿箱</h2>
      <el-dropdown data-test="create-btn" trigger="click" @command="onCreateCommand">
        <el-button type="primary">新建</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="blank">空白程序</el-dropdown-item>
            <el-dropdown-item command="word">从 Word 导入</el-dropdown-item>
            <el-dropdown-item command="batch" divided>批量导入（多个 Word）</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 空态由 ProcedureTable 内置 #empty 统一提供，避免与外层重复。 -->
    <ProcedureTable :rows="rows" :loading="loading" @open="open" />

    <el-pagination
      class="pager"
      layout="total, prev, pager, next"
      :total="total"
      :current-page="page"
      :page-size="pageSize"
      @current-change="onPage"
    />

    <CreateProcedureDialog v-model="createVisible" @created="onCreated" />
    <CreateFromWordDialog v-model="wordVisible" @imported="onImported" />
  </div>
</template>

<style scoped>
.drafts {
  padding: 20px 24px;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.title {
  margin: 0;
  font-size: 18px;
}
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
