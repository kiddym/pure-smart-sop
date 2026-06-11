<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <div class="auth-layout">
    <div class="auth-stage">
      <!-- 品牌字标：暗色工业风，六角螺母徽标 + Space Grotesk 字标 -->
      <div class="auth-brand u-fade-in">
        <span class="auth-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
            <path
              d="M12 2.5 20.5 7.25v9.5L12 21.5 3.5 16.75v-9.5L12 2.5Z"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linejoin="round"
            />
            <circle cx="12" cy="12" r="3.4" stroke="currentColor" stroke-width="1.6" />
          </svg>
        </span>
        <span class="auth-wordmark">{{ t('app.name') }}</span>
      </div>
      <p class="auth-tagline u-fade-in">结构化 SOP 程序管理平台</p>

      <div class="auth-card u-fade-in">
        <slot />
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-layout {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
  background: var(--bg-base);
  overflow: hidden;
}
/* 氛围层①：顶部赤陶径向光晕（不抢焦点的暖意） */
.auth-layout::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(120% 80% at 50% -10%, rgba(217, 119, 87, 0.14), transparent 60%),
    radial-gradient(80% 60% at 50% 120%, rgba(217, 119, 87, 0.06), transparent 55%);
  pointer-events: none;
}
/* 氛围层②：极淡工程网格纹（工业纸感，靠近不可见，远观成质感） */
.auth-layout::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--border-subtle) 1px, transparent 1px),
    linear-gradient(90deg, var(--border-subtle) 1px, transparent 1px);
  background-size: 40px 40px;
  opacity: 0.25;
  mask-image: radial-gradient(110% 110% at 50% 40%, #000 30%, transparent 75%);
  pointer-events: none;
}

.auth-stage {
  position: relative;
  z-index: 1;
  width: 360px;
  max-width: 100%;
}

/* —— 品牌区 —— */
.auth-brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 6px;
}
.auth-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  color: var(--accent);
  background: var(--accent-bg);
  border: 1px solid color-mix(in srgb, var(--accent) 35%, transparent);
  border-radius: 8px;
}
.auth-wordmark {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 22px;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}
.auth-tagline {
  margin: 0 0 24px;
  text-align: center;
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
  animation-delay: 0.04s;
}

/* —— 卡片：暗色工业面板（线 + 顶部赤陶标识条，深色友好软投影） —— */
.auth-card {
  padding: 32px 28px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-top: 2px solid var(--accent);
  border-radius: 8px;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.32);
  animation-delay: 0.08s;
}
</style>

<!-- 非 scoped：统一 auth 页内链接为赤陶 accent（修复 router-link 默认蓝紫），
     命名空间限定在 .auth-layout 内，不泄漏到全局。 -->
<style>
.auth-layout a {
  color: var(--accent);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.15s var(--ease-standard, ease);
}
.auth-layout a:hover {
  color: var(--el-color-primary-dark-2, var(--accent));
  text-decoration: underline;
}
</style>
