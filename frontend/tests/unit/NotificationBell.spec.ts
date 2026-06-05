import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import NotificationBell from '@/components/NotificationBell.vue'
import { useNotificationStore } from '@/store/notifications'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

// el-badge stub that renders both its :value prop and the slot content,
// so `w.text()` will include the badge number.
const badgeStub = {
  template: '<div>{{ value }}<slot /></div>',
  props: ['value', 'hidden', 'max'],
}
// el-dropdown stub renders both default slot and named #dropdown slot so the
// list items (inside #dropdown) are included in w.text() / w.find().
const dropdownStub = {
  template: '<div><slot /><slot name="dropdown" /></div>',
}
const slot = { template: '<div><slot /></div>' }

function mountBell() {
  return mount(NotificationBell, {
    global: {
      stubs: {
        'el-dropdown': dropdownStub,
        'el-dropdown-menu': slot,
        'el-badge': badgeStub,
        'el-icon': slot,
        'el-button': slot,
        'router-link': slot,
      },
    },
  })
}

describe('NotificationBell', () => {
  beforeEach(() => { setActivePinia(createPinia()); push.mockReset() })

  it('未读>0 显示数字角标', () => {
    const s = useNotificationStore()
    s.unreadCount = 5
    const w = mountBell()
    expect(w.text()).toContain('5')
  })

  it('渲染 recent 文案', () => {
    const s = useNotificationStore()
    s.recent = [{
      id: 'n1', type: 'WO_ASSIGNED', entity_type: 'work_order', entity_id: 'wo1',
      params: { custom_id: 'C-1', title: '巡检' }, actor_user_id: null, is_read: false, read_at: null,
      created_at: '2026-06-05T00:00:00',
    }]
    const w = mountBell()
    expect(w.text()).toContain('C-1')
  })

  it('点击条目 markRead + 跳转', async () => {
    const s = useNotificationStore()
    s.recent = [{
      id: 'n1', type: 'WO_ASSIGNED', entity_type: 'work_order', entity_id: 'wo1',
      params: { custom_id: 'C-1' }, actor_user_id: null, is_read: false, read_at: null,
      created_at: '2026-06-05T00:00:00',
    }]
    const markRead = vi.spyOn(s, 'markRead').mockResolvedValue()
    const w = mountBell()
    await w.find('[data-test="notif-item"]').trigger('click')
    expect(markRead).toHaveBeenCalledWith('n1')
    expect(push).toHaveBeenCalledWith({ name: 'maintenance-work-order-detail', params: { id: 'wo1' } })
  })
})
