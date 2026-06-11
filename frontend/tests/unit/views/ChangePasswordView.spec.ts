import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'
import ChangePasswordView from '@/views/auth/ChangePasswordView.vue'
import * as authApi from '@/api/auth'

function mountView() {
  return mount(ChangePasswordView, { global: { plugins: [ElementPlus, i18n] } })
}

describe('ChangePasswordView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('完整填写且一致时调用 changePassword 并清空表单', async () => {
    const spy = vi.spyOn(authApi, 'changePassword').mockResolvedValue()
    const w = mountView()
    await w.find('[data-test="old-password"]').setValue('oldpw123')
    await w.find('[data-test="new-password"]').setValue('newpw12345')
    await w.find('[data-test="confirm-password"]').setValue('newpw12345')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()
    expect(spy).toHaveBeenCalledWith('oldpw123', 'newpw12345')
    // 成功后清空
    expect((w.find('[data-test="new-password"]').element as HTMLInputElement).value).toBe('')
  })

  it('新密码不足 8 位不提交', async () => {
    const spy = vi.spyOn(authApi, 'changePassword').mockResolvedValue()
    const w = mountView()
    await w.find('[data-test="old-password"]').setValue('oldpw123')
    await w.find('[data-test="new-password"]').setValue('short')
    await w.find('[data-test="confirm-password"]').setValue('short')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()
    expect(spy).not.toHaveBeenCalled()
  })

  it('两次新密码不一致不提交', async () => {
    const spy = vi.spyOn(authApi, 'changePassword').mockResolvedValue()
    const w = mountView()
    await w.find('[data-test="old-password"]').setValue('oldpw123')
    await w.find('[data-test="new-password"]').setValue('newpw12345')
    await w.find('[data-test="confirm-password"]').setValue('different99')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()
    expect(spy).not.toHaveBeenCalled()
  })

  it('后端报错时在当前密码字段内联展示错误', async () => {
    vi.spyOn(authApi, 'changePassword').mockRejectedValue({
      response: { data: { detail: { message: '当前密码不正确' } } },
    })
    const w = mountView()
    await w.find('[data-test="old-password"]').setValue('wrongpw1')
    await w.find('[data-test="new-password"]').setValue('newpw12345')
    await w.find('[data-test="confirm-password"]').setValue('newpw12345')
    await w.find('[data-test="submit"]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('当前密码不正确')
  })
})
