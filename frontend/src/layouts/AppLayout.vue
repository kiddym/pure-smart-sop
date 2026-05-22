<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Document, EditPen, Folder } from '@element-plus/icons-vue'

const route = useRoute()
// 顶层菜单高亮：详情页 /procedures/:id 归到「程序库」
const activeMenu = computed(() => {
  if (route.path.startsWith('/folders')) return '/folders'
  if (route.path.startsWith('/procedures/drafts')) return '/procedures/drafts'
  return '/procedures/library'
})
</script>

<template>
  <el-container class="app-layout">
    <el-aside width="220px" class="app-aside">
      <div class="app-brand">Smart SOP</div>
      <el-menu :default-active="activeMenu" router class="app-menu">
        <el-menu-item index="/procedures/library">
          <el-icon><Document /></el-icon>
          <span>程序库</span>
        </el-menu-item>
        <el-menu-item index="/procedures/drafts">
          <el-icon><EditPen /></el-icon>
          <span>草稿箱</span>
        </el-menu-item>
        <el-menu-item index="/folders">
          <el-icon><Folder /></el-icon>
          <span>标准文件库</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main class="app-main">
      <RouterView />
    </el-main>
  </el-container>
</template>

<style scoped>
.app-layout {
  height: 100vh;
}
.app-aside {
  background: var(--bg-surface);
  display: flex;
  flex-direction: column;
}
.app-brand {
  color: var(--text-primary);
  font-size: 18px;
  font-weight: 600;
  padding: 18px 20px;
  letter-spacing: 0.5px;
}
.app-menu {
  border-right: none;
  background: transparent;
  flex: 1;
}
.app-main {
  padding: 20px 24px;
  background: #faf8f4;
  overflow: auto;
}
</style>
