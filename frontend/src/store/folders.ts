import { defineStore } from 'pinia'
import { fetchFolderOptions, fetchFolderTree } from '@/api/folders'
import type { FolderOption, FolderTreeNode } from '@/types/folder'

export const useFolderStore = defineStore('folders', {
  state: () => ({
    tree: [] as FolderTreeNode[],
    options: [] as FolderOption[],
    loading: false,
  }),
  actions: {
    async loadTree(): Promise<void> {
      this.loading = true
      try {
        this.tree = await fetchFolderTree()
      } finally {
        this.loading = false
      }
    },
    async loadOptions(): Promise<void> {
      this.options = await fetchFolderOptions()
    },
  },
})
