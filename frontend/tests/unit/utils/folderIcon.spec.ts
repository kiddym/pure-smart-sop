import { describe, expect, it } from 'vitest'
import { Folder, FolderOpened, Lock } from '@element-plus/icons-vue'
import { folderIcon } from '@/utils/folderIcon'

const leaf = { system: false, children: [] }
const branch = { system: false, children: [{ id: 'c' }] }
const sys = { system: true, children: [{ id: 'c' }] }

describe('folderIcon', () => {
  it('uses the lock icon for system folders (regardless of expand state)', () => {
    expect(folderIcon(sys, true)).toBe(Lock)
    expect(folderIcon(sys, false)).toBe(Lock)
  })

  it('uses the open folder when an ordinary folder with children is expanded', () => {
    expect(folderIcon(branch, true)).toBe(FolderOpened)
  })

  it('uses the closed folder when collapsed', () => {
    expect(folderIcon(branch, false)).toBe(Folder)
  })

  it('uses the closed folder for a childless folder even when "expanded"', () => {
    expect(folderIcon(leaf, true)).toBe(Folder)
  })
})
