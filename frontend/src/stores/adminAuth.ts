import { defineStore } from "pinia";
import { api } from "../services/api";

export const useAdminAuthStore = defineStore("adminAuth", {
  state: () => ({
    token: localStorage.getItem("uni_admin_token") ?? "",
    loading: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token),
  },
  actions: {
    async login(login: string, password: string) {
      this.loading = true;
      try {
        const { data } = await api.post("/api/admin/login", { login, password });
        const t = typeof data.token === "string" ? data.token.trim().replace(/^[\"']|[\"']$/g, "") : "";
        if (!t) throw new Error("Empty token");
        this.token = t;
        localStorage.setItem("uni_admin_token", t);
      } finally {
        this.loading = false;
      }
    },
    logout() {
      this.token = "";
      localStorage.removeItem("uni_admin_token");
    },
  },
});
