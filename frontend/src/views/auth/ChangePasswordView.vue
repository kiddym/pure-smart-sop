<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { changePassword } from '@/api/auth'
import { errorMessage } from '@/api/http'

const { t } = useI18n()

const formRef = ref<FormInstance>()
const form = ref({ oldPassword: '', newPassword: '', confirm: '' })
const submitting = ref(false)

const rules: FormRules = {
  oldPassword: [{ required: true, message: () => t('auth.required'), trigger: 'blur' }],
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
  if (!form.value.oldPassword || !form.value.newPassword) {
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
    await changePassword(form.value.oldPassword, form.value.newPassword)
    ElMessage.success(t('auth.changeSuccess'))
    form.value.oldPassword = ''
    form.value.newPassword = ''
    form.value.confirm = ''
    formRef.value?.clearValidate()
  } catch (err) {
    // 旧密码错误等后端校验：在当前密码字段上给出内联反馈，而非仅顶部 toast。
    const msg = errorMessage(err) ?? t('auth.changeFailed')
    ElMessage.error(msg)
    // 通过 el-form-item 的 :error 绑定在当前密码字段下方内联展示。
    oldPasswordError.value = msg
  } finally {
    submitting.value = false
  }
}

// 后端返回的当前密码错误内联展示。输入变化时清除。
const oldPasswordError = ref('')
</script>

<template>
  <div class="change-password-view">
    <el-card class="cp-card">
      <template #header>
        <span>{{ t('auth.changeTitle') }}</span>
      </template>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" @submit.prevent="submit">
        <el-form-item :label="t('auth.oldPassword')" prop="oldPassword">
          <el-input
            v-model="form.oldPassword"
            data-test="old-password"
            type="password"
            show-password
            autocomplete="current-password"
            @input="oldPasswordError = ''"
          />
          <!-- 后端返回的当前密码错误等内联反馈（el-form-item 的 :error 仅在内部校验态生效，故手动渲染）。 -->
          <div v-if="oldPasswordError" class="field-error" data-test="old-password-error">
            {{ oldPasswordError }}
          </div>
        </el-form-item>
        <el-form-item :label="t('auth.newPassword')" prop="newPassword">
          <el-input v-model="form.newPassword" data-test="new-password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item :label="t('auth.confirmPassword')" prop="confirm">
          <el-input v-model="form.confirm" data-test="confirm-password" type="password" show-password autocomplete="new-password" @keyup.enter="submit" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" data-test="submit" @click="submit">
            {{ t('auth.changeSubmit') }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.change-password-view { padding: 24px; }
.cp-card { max-width: 520px; }
.field-error {
  width: 100%;
  margin-top: 2px;
  color: var(--el-color-danger);
  font-size: 12px;
  line-height: 1.4;
}
</style>
