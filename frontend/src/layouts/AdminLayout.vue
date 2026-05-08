<script setup lang="ts">
import { useRouter } from "vue-router";
import { LayoutDashboard, GraduationCap, UsersRound, LogOut } from "lucide-vue-next";
import { useAdminAuthStore } from "../stores/adminAuth";

const auth = useAdminAuthStore();
const router = useRouter();

const logout = () => {
  auth.logout();
  router.push("/");
};
</script>

<template>
  <div class="flex min-h-screen bg-page-mist text-charcoal">
    <aside class="w-72 border-r border-matte-lilac/90 bg-white/95 p-4 shadow-sm">
      <h2 class="mb-8 text-2xl font-semibold text-[#5e4b7a]">UNI Admin</h2>
      <nav class="space-y-2">
        <router-link
          to="/admin/dashboard"
          class="flex items-center gap-2 rounded-xl px-3 py-2 hover:bg-matte-dust/80"
        >
          <LayoutDashboard class="h-4 w-4" /> Дашборд
        </router-link>
        <router-link
          to="/admin/universities"
          class="flex items-center gap-2 rounded-xl px-3 py-2 hover:bg-matte-dust/80"
        >
          <GraduationCap class="h-4 w-4" /> Вузы
        </router-link>
        <router-link
          to="/admin/students"
          class="flex items-center gap-2 rounded-xl px-3 py-2 hover:bg-matte-dust/80"
        >
          <UsersRound class="h-4 w-4" /> Управление выпускниками
        </router-link>
      </nav>
      <button
        class="mt-8 flex w-full items-center gap-2 rounded-xl border border-matte-lilac bg-white px-3 py-2 hover:bg-matte-dust/60"
        @click="logout"
      >
        <LogOut class="h-4 w-4" /> Выйти
      </button>
    </aside>
    <main class="flex-1 p-6">
      <router-view />
    </main>
  </div>
</template>
