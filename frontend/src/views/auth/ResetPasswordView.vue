<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { resetPassword } from '@/api/auth'
import { errorMessage } from '@/api/http'
import AuthLayout from '@/layouts/AuthLayout.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const formRef = ref<FormInstance>()
const form = ref({ token: '', newPassword: '', confirm: '' })
const submitting = ref(false)

// token 来自 URL query 时不应暴露为可编辑输入；仅当缺失时降级显示输入框。
const tokenFromUrl = ref(false)
const showTokenInput = computed(() => !tokenFromUrl.value)

onMounted(() => {
  const token = (route.query.token as string) || ''
  form.value.token = token
  tokenFromUrl.value = !!token
})

const rules: FormRules = {
  token: [{ required: true, message: () => t('auth.required'), trigger: 'blur' }],
  newPassword: [
    { required: true, message: () => t('auth.required'), trigger: 'blur' },
    { min: 8, message: () => t('auth.passwordTooShort'), trigger: ['blur', 'change'] },
  ],
  confirm: [
    { required: true, message: () => t('auth.required'), trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        if (value !== form.value.newPassword) callback(new Error(t('auth.passwordMismatch')))
        else callback()
      },
      trigger: ['blur', 'change'],
    },
  ],
}

async function submit(): Promise<void> {
  // 触发字段级内联校验提示（供真实浏览器使用）。
  formRef.value?.validate().catch(() => {})
  if (!form.value.token || !form.value.newPassword) {
    ElMessage.warning(t('auth.fillAllFields'))
    return
  }
  if (form.value.newPassword.length < 8) {
    ElMessage.warning(t('auth.passwordTooShort'))
    return
  }
  if (form.value.newPassword !== form.value.confirm) {
    ElMessage.warning(t('auth.passwordMismatch'))
    return
  }
  submitting.value = true
  try {
    await resetPassword(form.value.token, form.value.newPassword)
    ElMessage.success(t('auth.resetSuccess'))
    await router.push({ name: 'login' })
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.resetFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.resetTitle') }}</h2>
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="submit">
      <el-form-item v-if="showTokenInput" :label="t('auth.resetToken')" prop="token">
        <el-input v-model="form.token" data-test="token" />
      </el-form-item>
      <el-form-item :label="t('auth.newPassword')" prop="newPassword">
        <el-input v-model="form.newPassword" data-test="new-password" type="password" show-password autocomplete="new-password" />
      </el-form-item>
      <el-form-item :label="t('auth.confirmPassword')" prop="confirm">
        <el-input v-model="form.confirm" data-test="confirm-password" type="password" show-password autocomplete="new-password" @keyup.enter="submit" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-test="submit" style="width: 100%" @click="submit">
        {{ t('auth.resetSubmit') }}
      </el-button>
      <div class="auth-foot">
        <router-link :to="{ name: 'login' }">{{ t('auth.backToLogin') }}</router-link>
      </div>
    </el-form>
  </AuthLayout>
</template>

<style scoped>
.auth-title { margin: 0 0 24px; text-align: center; }
.auth-foot { margin-top: 16px; text-align: center; font-size: 13px; color: var(--text-tertiary); }
</style>
