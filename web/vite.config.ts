import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // 监听 0.0.0.0，允许局域网 IP（手机/其他设备）访问
    port: 5173,
    proxy: {
      // 只代理后端 API 前缀，不能写成 "/staff" / "/admin"，否则会拦截
      // 前端 SPA 页面路由（/staff/login、/admin/prompts 等）导致 404。
      "/api": "http://localhost:8000",
      "/staff/api": "http://localhost:8000",
      "/admin/api": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: [],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "cobertura"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/main.tsx", "src/**/*.d.ts", "tests/**"],
      thresholds: {
        lines: 75,
        functions: 75,
        branches: 70,
        statements: 75,
        autoUpdate: false,
      },
    },
  },
});
