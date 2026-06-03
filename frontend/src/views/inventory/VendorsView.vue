<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listVendors, createVendor, updateVendor, deleteVendor } from '@/api/vendors'
import { listPartsMini } from '@/api/parts'
import { listAssetsMini } from '@/api/assets'
import { listLocationsMini } from '@/api/locations'
import type { VendorRead, VendorCreate, VendorUpdate, PartMini } from '@/types/inventory'
import type { AssetMini, LocationMini } from '@/types/maindata'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

// ── state ──────────────────────────────────────────────────
const loading = ref(false)
const vendors = ref<VendorRead[]>([])
const partsMini = ref<PartMini[]>([])
const assetsMini = ref<AssetMini[]>([])
const locationsMini = ref<LocationMini[]>([])

// ── fetch ──────────────────────────────────────────────────
async function fetchVendors() {
  loading.value = true
  try {
    vendors.value = await listVendors()
  } finally {
    loading.value = false
  }
}

async function fetchPartsMini() {
  partsMini.value = await listPartsMini()
}

async function fetchAssetsMini() {
  assetsMini.value = await listAssetsMini()
}

async function fetchLocationsMini() {
  locationsMini.value = await listLocationsMini()
}

onMounted(async () => {
  await Promise.all([fetchVendors(), fetchPartsMini(), fetchAssetsMini(), fetchLocationsMini()])
})

// ── dialog ─────────────────────────────────────────────────
type DialogMode = 'create' | 'edit'

const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('create')
const editingId = ref<string | null>(null)
const submitting = ref(false)

interface FormState {
  name: string
  vendor_type: string
  description: string
  rate: string
  address: string
  phone: string
  email: string
  website: string
  part_ids: string[]
  asset_ids: string[]
  location_ids: string[]
}

const form = reactive<FormState>({
  name: '',
  vendor_type: '',
  description: '',
  rate: '',
  address: '',
  phone: '',
  email: '',
  website: '',
  part_ids: [],
  asset_ids: [],
  location_ids: [],
})

const dialogTitle = computed(() => (dialogMode.value === 'create' ? '新建供应商' : '编辑供应商'))

function resetForm() {
  form.name = ''
  form.vendor_type = ''
  form.description = ''
  form.rate = ''
  form.address = ''
  form.phone = ''
  form.email = ''
  form.website = ''
  form.part_ids = []
  form.asset_ids = []
  form.location_ids = []
}

function openCreate() {
  resetForm()
  dialogMode.value = 'create'
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row: VendorRead) {
  resetForm()
  Object.assign(form, {
    ...row,
    part_ids: [...row.part_ids],
    asset_ids: [...row.asset_ids],
    location_ids: [...row.location_ids],
  })
  dialogMode.value = 'edit'
  editingId.value = row.id
  dialogVisible.value = true
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写名称')
    return
  }

  submitting.value = true
  try {
    const payload: VendorCreate | VendorUpdate = {
      name: form.name.trim(),
      vendor_type: form.vendor_type,
      description: form.description,
      rate: form.rate,
      address: form.address,
      phone: form.phone,
      email: form.email,
      website: form.website,
      part_ids: form.part_ids,
      asset_ids: form.asset_ids,
      location_ids: form.location_ids,
    }
    if (dialogMode.value === 'create') {
      await createVendor(payload as VendorCreate)
      ElMessage.success('供应商创建成功')
    } else {
      if (!editingId.value) return
      await updateVendor(editingId.value, payload)
      ElMessage.success('供应商更新成功')
    }
    dialogVisible.value = false
    await fetchVendors()
  } catch {
    ElMessage.error('保存失败，请重试')
  } finally {
    submitting.value = false
  }
}

// ── delete ─────────────────────────────────────────────────
async function handleDelete(row: VendorRead) {
  try {
    await ElMessageBox.confirm(`确认删除供应商「${row.name}」？`, '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteVendor(row.id)
    ElMessage.success('已删除')
    await fetchVendors()
  } catch {
    // cancelled or error handled by interceptor
  }
}
</script>

<template>
  <div class="page">
    <h2 class="page-title">供应商管理</h2>

    <!-- toolbar -->
    <div class="toolbar">
      <el-button v-if="auth.hasPermission('vendor.create')" type="primary" @click="openCreate">
        新建供应商
      </el-button>
    </div>

    <!-- vendors table -->
    <el-table
      v-loading="loading"
      :data="vendors"
      row-key="id"
      border
      style="width: 100%; margin-top: 16px"
    >
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column prop="vendor_type" label="类型" min-width="120" />
      <el-table-column prop="rate" label="评分" min-width="100" />
      <el-table-column prop="phone" label="电话" min-width="140" />
      <el-table-column prop="email" label="邮箱" min-width="180" />
      <el-table-column label="操作" width="160" align="center" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="auth.hasPermission('vendor.edit')"
            link
            type="primary"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="auth.hasPermission('vendor.delete')"
            link
            type="danger"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- create / edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form label-width="90px" @submit.prevent="submitForm">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="请输入名称" />
        </el-form-item>

        <el-form-item label="类型">
          <el-input v-model="form.vendor_type" placeholder="请输入类型" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>

        <el-form-item label="评分">
          <el-input v-model="form.rate" placeholder="请输入评分" />
        </el-form-item>

        <el-form-item label="地址">
          <el-input v-model="form.address" placeholder="请输入地址" />
        </el-form-item>

        <el-form-item label="电话">
          <el-input v-model="form.phone" placeholder="请输入电话" />
        </el-form-item>

        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>

        <el-form-item label="网址">
          <el-input v-model="form.website" placeholder="请输入网址" />
        </el-form-item>

        <el-form-item label="关联备件">
          <el-select
            v-model="form.part_ids"
            multiple
            filterable
            placeholder="请选择关联备件"
            style="width: 100%"
          >
            <el-option v-for="p in partsMini" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="关联资产">
          <el-select
            v-model="form.asset_ids"
            multiple
            filterable
            placeholder="请选择关联资产"
            style="width: 100%"
          >
            <el-option v-for="a in assetsMini" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="关联位置">
          <el-select
            v-model="form.location_ids"
            multiple
            filterable
            placeholder="请选择关联位置"
            style="width: 100%"
          >
            <el-option v-for="l in locationsMini" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm"> 保存 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  max-width: 1100px;
  padding: 20px 24px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 20px;
  color: var(--text-primary, #1a1a1a);
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
