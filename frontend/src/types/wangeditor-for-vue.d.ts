// @wangeditor/editor-for-vue v5 的类型在 package.json exports 下无法被 bundler 解析，
// 这里补一个最小声明（组件以宽松 Component 暴露；编辑器实例类型仍取自 @wangeditor/editor）。
declare module '@wangeditor/editor-for-vue' {
  import type { Component } from 'vue'
  export const Editor: Component
  export const Toolbar: Component
}
