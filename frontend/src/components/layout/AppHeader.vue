<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { Menu, UserCircle2, X } from "lucide-vue-next";
import { useAdminAuthStore } from "../../stores/adminAuth";

const auth = useAdminAuthStore();
const router = useRouter();
const mobileOpen = ref(false);
const adminOpen = ref(false);

const navItems = [
  { to: "/dashboard", label: "Дашборд" },
  { to: "/universities", label: "Вузы" },
  { to: "/articles", label: "Статьи" },
  { to: "/about", label: "О проекте" },
];

const isAdmin = computed(() => auth.isAuthenticated);

const logout = () => {
  auth.logout();
  adminOpen.value = false;
  router.push("/");
};
</script>

<template>
  <header class="sticky top-0 z-30 border-b border-matte-lilac/80 bg-white/90 backdrop-blur-md">
    <div class="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 md:px-6">
      <router-link to="/" class="text-2xl font-semibold tracking-wide text-[#5e4b7a]">UNI</router-link>

      <nav class="hidden items-center gap-6 md:flex">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="rounded-full px-3 py-1.5 text-sm text-charcoal transition hover:bg-pastel-blue/40"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <div class="hidden items-center gap-3 md:flex">
        <router-link
          v-if="!isAdmin"
          to="/admin/login"
          class="rounded-full border border-[#c3b1e1] bg-ivory px-4 py-2 text-sm font-medium text-[#5e4b7a] hover:bg-pastel-lavender/40"
        >
          Вход для администратора
        </router-link>
        <div v-else class="relative">
          <button
            class="flex items-center gap-2 rounded-full border border-pastel-mint bg-white px-3 py-1.5 text-sm hover:bg-pastel-mint/40"
            @click="adminOpen = !adminOpen"
          >
            <UserCircle2 class="h-4 w-4 text-[#4f706e]" /> Администратор
          </button>
          <div v-if="adminOpen" class="absolute right-0 mt-2 w-64 rounded-2xl bg-white p-2 shadow-soft">
            <router-link class="block rounded-xl px-3 py-2 text-sm hover:bg-pastel-lavender/40" to="/admin/universities">
              Управление вузами
            </router-link>
            <router-link class="block rounded-xl px-3 py-2 text-sm hover:bg-pastel-blue/40" to="/admin/students">
              Управление выпускниками
            </router-link>
            <router-link class="block rounded-xl px-3 py-2 text-sm hover:bg-pastel-rose/40" to="/admin/articles">
              Управление статьями
            </router-link>
            <button class="mt-1 w-full rounded-xl bg-pastel-peach/50 px-3 py-2 text-left text-sm hover:bg-pastel-peach" @click="logout">
              Выйти
            </button>
          </div>
        </div>
      </div>

      <button class="rounded-xl border border-pastel-lavender p-2 md:hidden" @click="mobileOpen = !mobileOpen">
        <Menu v-if="!mobileOpen" class="h-4 w-4" />
        <X v-else class="h-4 w-4" />
      </button>
    </div>

    <div v-if="mobileOpen" class="border-t border-pastel-lavender/60 bg-ivory px-4 py-3 md:hidden">
      <div class="space-y-2">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="block rounded-xl px-3 py-2 text-sm hover:bg-pastel-blue/40"
          @click="mobileOpen = false"
        >
          {{ item.label }}
        </router-link>
        <router-link
          v-if="!isAdmin"
          to="/admin/login"
          class="block rounded-xl border border-[#c3b1e1] px-3 py-2 text-sm text-[#5e4b7a]"
          @click="mobileOpen = false"
        >
          Вход для администратора
        </router-link>
        <template v-else>
          <router-link to="/admin/universities" class="block rounded-xl px-3 py-2 text-sm hover:bg-pastel-lavender/40">Управление вузами</router-link>
          <router-link to="/admin/students" class="block rounded-xl px-3 py-2 text-sm hover:bg-pastel-blue/40">Управление выпускниками</router-link>
          <router-link to="/admin/articles" class="block rounded-xl px-3 py-2 text-sm hover:bg-pastel-rose/40">Управление статьями</router-link>
          <button class="w-full rounded-xl bg-pastel-peach/60 px-3 py-2 text-left text-sm" @click="logout">Выйти</button>
        </template>
      </div>
    </div>
  </header>
</template>
