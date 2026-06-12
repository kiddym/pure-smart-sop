<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Files } from '@element-plus/icons-vue'

import { useBatchReviewStore } from '@/store/batchReview'
import { useVirtualRows } from '@/composables/useVirtualRows'
import { useBatchReviewShortcuts } from '@/composables/useBatchReviewShortcuts'
import BatchReviewRow from '@/components/batch/BatchReviewRow.vue'
import ReviewDrawer from '@/components/batch/ReviewDrawer.vue'
import ApplyPreviewDialog from '@/components/batch/ApplyPreviewDialog.vue'
import EmptyState from '@/components/shared/EmptyState.vue'

const route = useRoute()
const store = useBatchReviewStore()

const rowsEl = ref<HTMLElement | null>(null)
const drawerVisible = ref(false)
const drawerEditable = ref(false)
const previewVisible = ref(false)
const previewItemIds = ref<string[] | null>(null)
// store.load 无内置错误态，这里在 view 层捕获以支持重试。
const loadError = ref(false)

const rows = computed(() => store.riskSortedItems)
const { start, end, padTop, padBottom, totalHeight } = useVirtualRows(rowsEl, () => rows.value.length)

async function loadJob(): Promise<void> {
  loadError.value = false
  try {
    await store.load(route.params.jobId as string)
    if (store.inProgress) store.startPolling()
  } catch {
    loadError.value = true
  }
}

onMounted(loadJob)
onUnmounted(() => store.stopPolling())

// 「精审」打开可编辑抽屉；「预览」打开只读抽屉。两者共用同一抽屉组件，靠 editable 区分。
async function openReview(itemId: string, editable: boolean): Promise<void> {
  await store.openItem(itemId)
  drawerEditable.value = editable
  drawerVisible.value = true
}

function openApplyPreview(itemIds: string[] | null): void {
  previewItemIds.value = itemIds
  previewVisible.value = true
}

async function confirmApply(): Promise<void> {
  await store.apply({ itemIds: previewItemIds.value })
  previewVisible.value = false
  ElMessage.success('已提交应用，后台落库中')
}

function applyAllHighConfidence(): void {
  openApplyPreview(store.highConfidenceIds)
}

// 跳过为不可撤销的状态变更，加二次确认避免误触。
async function confirmSkip(itemId: string): Promise<void> {
  try {
    await ElMessageBox.confirm('跳过后该文件不会被导入，确定跳过？', '跳过确认', {
      type: 'warning',
    })
  } catch {
    return // 用户取消
  }
  await store.skip(itemId)
  ElMessage.success('已跳过')
}

useBatchReviewShortcuts({
  onPrev: () => store.selectPrev(),
  onNext: () => store.selectNext(),
  onOpen: () => { if (store.currentItemId) void openReview(store.currentItemId, true) },
  onApply: () => { if (store.currentItemId) openApplyPreview([store.currentItemId]) },
  onSkip: () => { if (store.currentItemId) void confirmSkip(store.currentItemId) },
})
</script>

<template>
  <div class="batch-review">
    <header v-if="store.job" class="summary">
      <span>待确认 {{ store.job.counts.review }}</span>
      <span>已应用 {{ store.job.counts.applied }}</span>
      <span>失败 {{ store.job.counts.failed }}</span>
      <el-button
        type="primary"
        :disabled="!store.highConfidenceIds.length"
        @click="applyAllHighConfidence"
      >全选高置信并应用（{{ store.highConfidenceIds.length }}）</el-button>
    </header>

    <!-- 错误态：load 失败可重试。 -->
    <el-result v-if="loadError" icon="error" title="加载失败" sub-title="批量审阅任务加载失败">
      <template #extra>
        <el-button type="primary" @click="loadJob">重试</el-button>
      </template>
    </el-result>

    <!-- 加载态：首次拉取期间。 -->
    <div v-else-if="store.loading" v-loading="true" class="loading-box" />

    <!-- 空态：无任何条目。 -->
    <EmptyState
      v-else-if="!rows.length"
      :icon="Files"
      title="暂无待审阅文件"
      description="该批量导入任务下没有可审阅的文件"
    />

    <div v-else ref="rowsEl" class="rows" :style="{ height: '70vh', overflow: 'auto' }">
      <div :style="{ height: totalHeight + 'px', position: 'relative' }">
        <div :style="{ height: padTop + 'px' }" />
        <BatchReviewRow
          v-for="item in rows.slice(start, end)"
          :key="item.id"
          :item="item"
          :selected="item.id === store.currentItemId"
          @open="openReview(item.id, false)"
          @edit="openReview(item.id, true)"
          @apply="openApplyPreview([item.id])"
          @skip="confirmSkip(item.id)"
          @retry="store.retry(item.id)"
        />
        <div :style="{ height: padBottom + 'px' }" />
      </div>
    </div>

    <ReviewDrawer v-model="drawerVisible" :editable="drawerEditable" />
    <ApplyPreviewDialog
      v-model="previewVisible"
      :item-ids="previewItemIds"
      @confirm="confirmApply"
    />
  </div>
</template>

<style scoped>
.loading-box {
  height: 70vh;
}
</style>
