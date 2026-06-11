<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
const token = ref('')
const form = ref({ name: '', password: '' })
const submitting = ref(false)

const rules: FormRules = {
  name: [{ required: true, message: () => t('auth.required'), trigger: 'blur' }],
  password: [
    { required: true, message: () => t('auth.required'), trigger: 'blur' },
    { min: 8, message: () => t('auth.passwordTooShort'), trigger: ['blur', 'change'] },
  ],
}

onMounted(() => {
  token.value = (route.query.token as string) || ''
  if (!token.value) ElMessage.warning(t('auth.missingToken'))
})

async function submit(): Promise<void> {
  if (!token.value) {
    ElMessage.warning(t('auth.missingToken'))
    return
  }
  // 触发字段级内联校验提示（供真实浏览器使用）。
  formRef.value?.validate().catch(() => {})
  if (!form.value.name || !form.value.password) {
    ElMessage.warning(t('auth.fillAllFields'))
    return
  }
  if (form.value.password.length < 8) {
    ElMessage.warning(t('auth.passwordTooShort'))
    return
  }
  submitting.value = true
  try {
    await auth.acceptInvite(token.value, form.value.name, form.value.password)
    await router.push('/')
  } catch (err) {
    ElMessage.error(errorMessage(err) ?? t('auth.acceptFailed'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AuthLayout>
    <h2 class="auth-title">{{ t('auth.acceptTitle') }}</h2>
    <p class="auth-hint">{{ t('auth.acceptHint') }}</p>
    <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="submit">
      <el-form-item :label="t('auth.name')" prop="name">
        <el-input v-model="form.name" data-test="name" autocomplete="name" />
      </el-form-item>
      <el-form-item :label="t('auth.password')" prop="password">
        <el-input v-model="form.password" data-test="password" type="password" show-password autocomplete="new-password" @keyup.enter="submit" />
      </el-form-item>
      <el-button type="primary" :loading="submitting" data-test="submit" style="width: 100%" @click="submit">
        {{ t('auth.acceptSubmit') }}
      </el-button>
      <div class="auth-foot">
        <router-link :to="{ name: 'login' }">{{ t('auth.backToLogin') }}</router-link>
      </div>
    </el-form>
  </AuthLayout>
</template>

<style scoped>
.auth-title { margin: 0 0 16px; text-align: center; }
.auth-hint { margin: 0 0 20px; text-align: center; font-size: 13px; color: var(--text-tertiary); }
.auth-foot { margin-top: 16px; text-align: center; font-size: 13px; color: var(--text-tertiary); }
</style>
