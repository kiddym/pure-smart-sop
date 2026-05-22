# Smart SOP Frontend

Vue 3 + Element Plus + Pinia + Vite + TypeScript。

## 目录结构

```
frontend/
├── src/
│   ├── main.ts              # 应用入口
│   ├── App.vue              # 根组件
│   ├── api/                 # 接口调用层（axios 薄封装）
│   ├── components/          # 全局复用组件
│   ├── views/               # 路由级页面
│   │   ├── procedure/       # 程序模块
│   │   └── settings/        # 设置模块
│   ├── store/               # Pinia 模块
│   ├── router/              # 路由配置
│   ├── types/               # 全局 TS 类型
│   ├── utils/               # 工具函数
│   ├── layouts/             # 布局组件
│   └── assets/              # 静态资源
├── public/
├── tests/                   # 单元测试 / e2e
├── index.html
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
├── postcss.config.js
├── package.json
├── Dockerfile
└── nginx.conf
```

> 大多数子目录目前为空，Phase 2 起开始填充。

## 开发指引

详见根目录 [`docs/deployment.md`](../docs/deployment.md) 与 [`docs/frontend-coding-standards.md`](../docs/frontend-coding-standards.md)。
