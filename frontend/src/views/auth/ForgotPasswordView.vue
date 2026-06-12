<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { forgotPassword } from '@/api/auth'
import { errorMessage } from '@/api/http'
import AuthLayout from '@/layouts/AuthLayout.vue'

const { t } = useI18n()

const formRef = ref<FormInstance>()
const form = ref({ email: '', companySlug: '' })
const submitting = ref(false)
const sent = ref(false)

const rules: FormRules = {
  email: [
    { required: true, message: () => t('auth.fillEmail'), trigger: 'blur' },
    { type: 'email', message: () => t('auth.emailInvalid'), trigger: ['blur', 'change'] },
  ],
}

async function submit(): Promise<void> {
  // 触发字段级内联校验提示（供真实浏览器使用）。
  formRef.value?.validate().catch(() => {})
  if (!form.value.email) {
    ElMessage.warning(t('auth.fillEmail'))
    return
  }
  submitting.value = true
  try {
    await forgotPassword(form.value.email, form.value.companySlug)
    sent.value = true
    ElMessage.success(t('auth.forgotSent'))
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.forgotFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.forgotTitle') }}</h2>
    <p v-if="!sent" class="auth-hint">{{ t('auth.forgotHint') }}</p>
    <p v-else class="auth-hint">{{ t('auth.forgotSent') }}</p>
    <el-form v-if="!sent" ref="formRef" :model="form" :rules="rules" @submit.prevent="submit">
      <el-form-item :label="t('auth.email')" prop="email">
        <el-input v-model="form.email" data-test="email" type="email" autocomplete="username" />
      </el-form-item>
      <el-form-item :label="t('auth.companySlugOptional')" prop="companySlug">
        <el-input v-model="form.companySlug" data-test="company-slug" @keyup.enter="submit" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-test="submit" style="width: 100%" @click="submit">
        {{ t('auth.sendResetLink') }}
      </el-button>
    </el-form>
    <div class="auth-foot">
      <router-link :to="{ name: 'login' }">{{ t('auth.backToLogin') }}</router-link>
    </div>
  </AuthLayout>
</template>

<style scoped>
.auth-title { margin: 0 0 16px; text-align: center; }
.auth-hint { margin: 0 0 20px; text-align: center; font-size: 13px; color: var(--text-tertiary); }
.auth-foot { margin-top: 16px; text-align: center; font-size: 13px; color: var(--text-tertiary); }
</style>
