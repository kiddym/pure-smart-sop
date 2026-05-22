import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/procedures/library' },
  {
    path: '/procedures/library',
    name: 'procedure-library',
    component: () => import('@/views/procedures/ProcedureLibraryView.vue'),
    meta: { title: '程序库' },
  },
  {
    path: '/procedures/drafts',
    name: 'procedure-drafts',
    component: () => import('@/views/procedures/ProcedureDraftsView.vue'),
    meta: { title: '草稿箱' },
  },
  {
    path: '/procedures/import',
    name: 'procedure-import',
    component: () => import('@/views/procedures/ImportWizardView.vue'),
    meta: { title: '导入程序' },
  },
  {
    path: '/procedures/:id/edit',
    name: 'procedure-edit',
    component: () => import('@/views/procedures/ProcedureEditorView.vue'),
    meta: { title: '编辑程序' },
  },
  {
    path: '/procedures/:id/view',
    name: 'procedure-view',
    component: () => import('@/views/procedures/ProcedureEditorView.vue'),
    meta: { title: '查看程序' },
  },
  {
    path: '/procedures/:id',
    name: 'procedure-detail',
    component: () => import('@/views/procedures/ProcedureDetailView.vue'),
    meta: { title: '程序详情' },
  },
  {
    path: '/folders',
    name: 'folder-manage',
    component: () => import('@/views/folders/FolderManageView.vue'),
    meta: { title: '标准文件库' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
