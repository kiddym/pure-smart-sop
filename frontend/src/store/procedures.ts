import { defineStore } from 'pinia'
import {
  fetchProcedureLibrary,
  fetchProcedureList,
  type ProcedureListQuery,
} from '@/api/procedures'
import type { ProcedureRow } from '@/types/procedure'

export const useProcedureStore = defineStore('procedures', {
  state: () => ({
    rows: [] as ProcedureRow[],
    total: 0,
    page: 1,
    pageSize: 20,
    loading: false,
  }),
  actions: {
    async loadList(query: ProcedureListQuery): Promise<void> {
      this.loading = true
      try {
        const res = await fetchProcedureList(query)
        this.rows = res.items
        this.total = res.total
        this.page = res.page
        this.pageSize = res.page_size
      } finally {
        this.loading = false
      }
    },
    async loadLibrary(query: ProcedureListQuery): Promise<void> {
      this.loading = true
      try {
        const res = await fetchProcedureLibrary(query)
        this.rows = res.items
        this.total = res.total
        this.page = res.page
        this.pageSize = res.page_size
      } finally {
        this.loading = false
      }
    },
  },
})
