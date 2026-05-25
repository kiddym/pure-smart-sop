import { useStorage } from '@vueuse/core'
import type { Ref } from 'vue'

// 模块级单例 → 同标签页内各组件共享同一响应式 ref（不依赖 storage 事件）。
// flush: 'sync' 确保 ref 变更立即落盘，避免异步刷新导致测试或极端时序下读取旧值。
const collapsed = useStorage<boolean>('smartsop.sidebar.collapsed', false, undefined, { flush: 'sync' })

export function useSidebar(): { collapsed: Ref<boolean>; toggle: () => void } {
  return {
    collapsed,
    toggle: (): void => {
      collapsed.value = !collapsed.value
    },
  }
}
