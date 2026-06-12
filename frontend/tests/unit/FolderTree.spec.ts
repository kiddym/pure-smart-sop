import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { Folder, FolderOpened, Lock } from '@element-plus/icons-vue'
import FolderTree from '@/components/FolderTree.vue'
import type { FolderTreeNode } from '@/types/folder'

function fnode(over: Partial<FolderTreeNode>): FolderTreeNode {
  return {
    id: 'x', name: '文件夹', prefix: '', parent_id: null, system: false,
    full_path: '', sequence_digits: 3, created_at: '', updated_at: '',
    procedure_count: 0, children: [], ...over,
  }
}

function mountTree(data: FolderTreeNode[]) {
  return mount(FolderTree, { props: { data }, global: { plugins: [ElementPlus] }, attachTo: document.body })
}

describe('FolderTree icons', () => {
  it('renders a lock icon for system folders', () => {
    const w = mountTree([fnode({ id: 's', name: '系统', system: true })])
    expect(w.findComponent(Lock).exists()).toBe(true)
  })

  it('renders an open folder for an expanded folder with children (default-expand-all)', () => {
    const w = mountTree([
      fnode({ id: 'a', name: '设备维护', children: [fnode({ id: 'b', name: '润滑' })] }),
    ])
    expect(w.findComponent(FolderOpened).exists()).toBe(true)
  })

  it('renders a closed folder for an ordinary childless folder', () => {
    const w = mountTree([fnode({ id: 'a', name: '点检' })])
    expect(w.findComponent(Folder).exists()).toBe(true)
  })
})
