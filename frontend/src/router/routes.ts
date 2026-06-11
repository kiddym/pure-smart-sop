import { type RouteRecordRaw } from 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    requiresAuth?: boolean
    requiredPermission?: string // 预留：权限框架就位但当前守卫不强制
  }
}

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/auth/RegisterView.vue'),
    meta: { title: '注册' },
  },
  {
    path: '/forgot-password',
    name: 'forgot-password',
    component: () => import('@/views/auth/ForgotPasswordView.vue'),
    meta: { title: '找回密码' },
  },
  {
    path: '/reset-password',
    name: 'reset-password',
    component: () => import('@/views/auth/ResetPasswordView.vue'),
    meta: { title: '重置密码' },
  },
  {
    path: '/accept-invite',
    name: 'accept-invite',
    component: () => import('@/views/auth/AcceptInviteView.vue'),
    meta: { title: '接受邀请' },
  },
  {
    path: '/verify-email',
    name: 'verify-email',
    component: () => import('@/views/auth/VerifyEmailView.vue'),
    meta: { title: '邮箱验证' },
  },
  {
    path: '/account/profile',
    name: 'account-profile',
    component: () => import('@/views/account/ProfileView.vue'),
    meta: { title: '个人资料', requiresAuth: true },
  },
  {
    path: '/account/change-password',
    name: 'change-password',
    component: () => import('@/views/auth/ChangePasswordView.vue'),
    meta: { title: '修改密码', requiresAuth: true },
  },
  { path: '/', redirect: '/procedures/library' },
  {
    path: '/procedures/library',
    name: 'procedure-library',
    component: () => import('@/views/procedures/ProcedureLibraryView.vue'),
    meta: { title: '程序库', requiresAuth: true },
  },
  {
    path: '/procedures/drafts',
    name: 'procedure-drafts',
    component: () => import('@/views/procedures/ProcedureDraftsView.vue'),
    meta: { title: '草稿箱', requiresAuth: true },
  },
  {
    path: '/procedures/folders',
    name: 'folder-manage',
    component: () => import('@/views/folders/FolderManageView.vue'),
    meta: { title: '文件夹配置', requiresAuth: true },
  },
  { path: '/folders', redirect: '/procedures/folders' },
  {
    path: '/procedures/:id/edit',
    name: 'procedure-edit',
    component: () => import('@/views/procedures/ProcedureEditorView.vue'),
    meta: { title: '编辑程序', requiresAuth: true },
  },
  {
    path: '/procedures/:id/view',
    name: 'procedure-view',
    component: () => import('@/views/procedures/ProcedureEditorView.vue'),
    meta: { title: '查看程序', requiresAuth: true },
  },
  {
    path: '/procedures/batch-review/:jobId',
    name: 'batch-review',
    component: () => import('@/views/procedures/BatchReviewView.vue'),
    meta: { title: '批量审阅台', requiresAuth: true },
  },
  {
    path: '/procedures/:id',
    name: 'procedure-detail',
    component: () => import('@/views/procedures/ProcedureDetailView.vue'),
    meta: { title: '程序详情', requiresAuth: true },
  },
  {
    path: '/admin/config',
    name: 'config-console',
    component: () => import('@/views/admin/config/ConfigConsoleView.vue'),
    meta: { title: '配置中心', requiresAuth: true },
  },
  {
    path: '/admin/config/sop',
    name: 'config-sop',
    component: () => import('@/views/admin/config/SopConfigView.vue'),
    meta: { title: 'SOP 配置', requiresAuth: true },
  },
  {
    path: '/admin/config/organization',
    name: 'config-organization',
    component: () => import('@/views/admin/config/OrganizationConfigView.vue'),
    meta: { title: '系统设置', requiresAuth: true },
  },
  {
    path: '/admin/settings',
    redirect: '/admin/config/organization',
  },
  { path: '/settings', redirect: '/admin/settings' },
  { path: '/admin/fields', redirect: { path: '/admin/config/sop', query: { tab: 'fields' } } },
  { path: '/settings/fields', redirect: '/admin/fields' },
  { path: '/admin/heading-rules', redirect: { path: '/admin/config/sop', query: { tab: 'heading-rules' } } },
  { path: '/settings/heading-rules', redirect: '/admin/heading-rules' },
  {
    path: '/admin/company',
    redirect: '/admin/config/organization',
  },
  { path: '/platform/settings', redirect: '/admin/company' },
]
