<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getCompanySettings, updateCompanySettings } from '@/api/companySettings'
import type { CompanySettingsUpdate } from '@/types/platform'
import { useAuthStore } from '@/store/auth'
import { useCompanySettingsStore } from '@/store/companySettings'

const auth = useAuthStore()
const companySettingsStore = useCompanySettingsStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const saving = ref(false)

const form = reactive<CompanySettingsUpdate>({
  date_format: '',
  timezone: '',
  auto_assign: false,
})

const canEdit = computed(() => auth.hasPermission('company.settings'))

const DATE_FORMATS = ['YYYY-MM-DD', 'YYYY/MM/DD', 'DD/MM/YYYY', 'MM/DD/YYYY']

// ── fetch ──────────────────────────────────────────────────
async function fetchSettings() {
  loading.value = true
  try {
    Object.assign(form, await getCompanySettings())
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await fetchSettings()
})

// ── save ───────────────────────────────────────────────────
async function handleSave() {
  try {
    saving.value = true
    const updated = await updateCompanySettings({ ...form })
    Object.assign(form, updated)
    // 同步轻量缓存。
    companySettingsStore.settings = updated
    ElMessage.success('保存成功')
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="company-settings-view">
    <h2 class="page-title">公司设置</h2>

    <el-form v-loading="loading" label-width="120px" class="settings-form">
      <el-form-item label="日期格式">
        <el-select
          v-model="form.date_format"
          :disabled="!canEdit"
          placeholder="请选择日期格式"
          style="width: 100%"
        >
          <el-option v-for="f in DATE_FORMATS" :key="f" :label="f" :value="f" />
        </el-select>
      </el-form-item>

      <el-form-item label="时区">
        <el-input v-model="form.timezone" :disabled="!canEdit" placeholder="如 Asia/Shanghai" />
      </el-form-item>

      <el-form-item label="自动派单">
        <el-switch v-model="form.auto_assign" :disabled="!canEdit" />
      </el-form-item>

      <el-form-item v-if="canEdit">
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.company-settings-view {
  max-width: 720px;
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary);
}
.settings-form {
  margin-top: 8px;
}
</style>
