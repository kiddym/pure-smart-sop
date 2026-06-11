<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/store/auth'
import { errorMessage } from '@/api/http'
import AuthLayout from '@/layouts/AuthLayout.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const form = ref({ email: '', password: '', companySlug: '' })
const submitting = ref(false)

const rules: FormRules = {
  email: [
    { required: true, message: () => t('auth.fillEmail'), trigger: 'blur' },
    { type: 'email', message: () => t('auth.emailInvalid'), trigger: ['blur', 'change'] },
  ],
  password: [
    { required: true, message: () => t('auth.required'), trigger: 'blur' },
  ],
}

async function submit(): Promise<void> {
  // 触发字段级内联校验提示（供真实浏览器使用）。
  formRef.value?.validate().catch(() => {})
  if (!form.value.email || !form.value.password) {
    ElMessage.warning(t('auth.fillEmailPassword'))
    return
  }
  submitting.value = true
  try {
    await auth.login({
      email: form.value.email,
      password: form.value.password,
      company_slug: form.value.companySlug || undefined,
    })
    const redirect = (route.query.redirect as string) || '/'
    await router.push(redirect)
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.loginFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.login') }}</h2>
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="submit">
      <el-form-item :label="t('auth.email')" prop="email">
        <el-input v-model="form.email" data-test="email" type="email" autocomplete="username" />
      </el-form-item>
      <el-form-item :label="t('auth.password')" prop="password">
        <el-input v-model="form.password" data-test="password" type="password" show-password autocomplete="current-password" @keyup.enter="submit" />
      </el-form-item>
      <el-form-item :label="t('auth.companySlugOptional')" prop="companySlug">
        <el-input v-model="form.companySlug" data-test="company-slug" autocomplete="organization" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-test="submit" style="width: 100%" @click="submit">
        {{ t('auth.login') }}
      </el-button>
      <div class="auth-foot">
        {{ t('auth.noAccount') }}
        <router-link :to="{ name: 'register' }">{{ t('auth.register') }}</router-link>
      </div>
      <div class="auth-foot">
        <router-link :to="{ name: 'forgot-password' }">{{ t('auth.forgotPassword') }}</router-link>
      </div>
    </el-form>
  </AuthLayout>
</template>

<style scoped>
.auth-title { margin: 0 0 24px; text-align: center; }
.auth-foot { margin-top: 16px; text-align: center; font-size: 13px; color: var(--text-tertiary); }
</style>
