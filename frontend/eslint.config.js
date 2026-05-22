import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import vue from 'eslint-plugin-vue'
import globals from 'globals'

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'coverage'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  // essential = 仅纠错规则；模板格式交给 Prettier，避免与 max-attributes-per-line 等冲突
  ...vue.configs['flat/essential'],
  {
    files: ['**/*.{ts,vue}'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.node },
      parserOptions: {
        // .vue 文件的 <script lang="ts"> 用 TS parser
        parser: tseslint.parser,
      },
    },
    rules: {
      // 沿用 Phase 0 .eslintrc 约定
      'vue/multi-word-component-names': 'off',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
  {
    // 测试文件放宽（vitest 全局 + 允许 any 桩）
    files: ['tests/**/*.{ts,spec.ts}'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
)
