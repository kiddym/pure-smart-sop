/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#409eff',
          dark: '#337ecc',
        },
      },
      fontFamily: {
        sans: [
          'PingFang SC',
          'Microsoft YaHei',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
    },
  },
  plugins: [],
  corePlugins: {
    // Element Plus 自带 preflight，避免冲突
    preflight: false,
  },
}
