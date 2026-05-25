import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// dev 代理后端地址：默认本地 8000，可用 VITE_API_PROXY 指向远端联调环境，无需改源码。
// 生产前端走相对路径同源部署，不经此代理。
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_PROXY || "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      host: true, // 监听 0.0.0.0，允许局域网 IP（手机/其他设备）访问
      port: 5173,
      proxy: {
        // 只代理后端 API 前缀，不能写成 "/staff" / "/admin"，否则会拦截
        // 前端 SPA 页面路由（/staff/login、/admin/prompts 等）导致 404。
        "/api": target,
        "/staff/api": target,
        "/admin/api": target,
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["tests/setup.ts"],
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
  };
});
