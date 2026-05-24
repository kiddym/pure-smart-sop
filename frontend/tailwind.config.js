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
          DEFAULT: '#d97757',
          dark: '#ae5f46',
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
        display: ['Fraunces', 'Georgia', 'Times New Roman', 'serif'],
      },
    },
  },
  plugins: [],
  corePlugins: {
    // Element Plus 自带 preflight，避免冲突
    preflight: false,
  },
}
