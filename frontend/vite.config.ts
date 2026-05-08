import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

const apiProxyTarget = process.env.VITE_PROXY_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  appType: "spa",
  plugins: [vue()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": { target: apiProxyTarget, changeOrigin: true },
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: false,
    proxy: {
      "/api": { target: apiProxyTarget, changeOrigin: true },
    },
  },
});
