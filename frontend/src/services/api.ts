import axios from "axios";
import { getActivePinia } from "pinia";

/** Убирает хвост `/api` у baseURL, чтобы не получить `/api/api/...`. */
function normalizeApiBase(raw: string): string {
  const trimmed = raw.replace(/\/+$/, "");
  if (trimmed.toLowerCase().endsWith("/api")) {
    return trimmed.slice(0, -4).replace(/\/+$/, "") || "";
  }
  return trimmed;
}

const baseURL = normalizeApiBase(import.meta.env.VITE_API_BASE_URL ?? "");

export const api = axios.create({
  baseURL,
  timeout: 120_000,
});

api.interceptors.request.use((config) => {
  const raw = localStorage.getItem("uni_admin_token");
  const token = typeof raw === "string" ? raw.trim().replace(/^[\"']|[\"']$/g, "") : "";
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error: unknown) => {
    if (!axios.isAxiosError(error) || !error.response || !error.config) {
      return Promise.reject(error);
    }
    const status = error.response.status;
    const reqUrl = `${error.config.baseURL ?? ""}${error.config.url ?? ""}`;
    const isAdminProtected =
      status === 401 && reqUrl.includes("/api/admin") && !reqUrl.includes("/api/admin/login");
    if (isAdminProtected) {
      localStorage.removeItem("uni_admin_token");
      const pinia = getActivePinia();
      try {
        if (pinia) {
          const { useAdminAuthStore } = await import("../stores/adminAuth");
          useAdminAuthStore(pinia).logout();
        }
      } catch {
        /* ignore */
      }
      try {
        const { default: router } = await import("../router/index");
        if (router.currentRoute.value.meta.requiresAuth) {
          await router.replace({
            name: "admin-login",
            query: { session: status === 401 ? "expired" : "error" },
          });
        }
      } catch {
        /* ignore */
      }
    }
    return Promise.reject(error);
  },
);
