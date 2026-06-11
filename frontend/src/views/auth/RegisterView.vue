<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { errorMessage } from '@/api/http'
import AuthLayout from '@/layouts/AuthLayout.vue'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const form = ref({ companyName: '', name: '', email: '', password: '' })
const submitting = ref(false)

const rules: FormRules = {
  companyName: [{ required: true, message: () => t('auth.required'), trigger: 'blur' }],
  name: [{ required: true, message: () => t('auth.required'), trigger: 'blur' }],
  email: [
    { required: true, message: () => t('auth.fillEmail'), trigger: 'blur' },
    { type: 'email', message: () => t('auth.emailInvalid'), trigger: ['blur', 'change'] },
  ],
  password: [
    { required: true, message: () => t('auth.required'), trigger: 'blur' },
    { min: 8, message: () => t('auth.passwordTooShort'), trigger: ['blur', 'change'] },
  ],
}

async function submit(): Promise<void> {
  // 触发字段级内联校验提示（供真实浏览器使用）。
  formRef.value?.validate().catch(() => {})
  // 显式守卫以保证行为确定（与 8 位口径一致）。
  if (
    !form.value.companyName ||
    !form.value.name ||
    !form.value.email ||
    form.value.password.length < 8
  ) {
    ElMessage.warning(t('auth.registerHint'))
    return
  }
  submitting.value = true
  try {
    await auth.register({
      company_name: form.value.companyName,
      name: form.value.name,
      email: form.value.email,
      password: form.value.password,
    })
    await router.push('/')
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.registerFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.register') }}</h2>
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="submit">
      <el-form-item :label="t('auth.companyName')" prop="companyName">
        <el-input v-model="form.companyName" data-test="companyName" autocomplete="organization" />
      </el-form-item>
      <el-form-item :label="t('auth.name')" prop="name">
        <el-input v-model="form.name" data-test="name" autocomplete="name" />
      </el-form-item>
      <el-form-item :label="t('auth.email')" prop="email">
        <el-input v-model="form.email" data-test="email" type="email" autocomplete="email" />
      </el-form-item>
      <el-form-item :label="t('auth.password')" prop="password">
        <el-input v-model="form.password" data-test="password" type="password" show-password autocomplete="new-password" @keyup.enter="submit" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-test="submit" style="width: 100%" @click="submit">
        {{ t('auth.register') }}
      </el-button>
      <div class="auth-foot">
        {{ t('auth.haveAccount') }}
        <router-link :to="{ name: 'login' }">{{ t('auth.login') }}</router-link>
      </div>
    </el-form>
  </AuthLayout>
</template>

<style scoped>
.auth-title { margin: 0 0 24px; text-align: center; }
.auth-foot { margin-top: 16px; text-align: center; font-size: 13px; color: var(--text-tertiary); }
</style>
