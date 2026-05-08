<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { toast } from "vue-sonner";
import { useAdminAuthStore } from "../../stores/adminAuth";

const login = ref("admin");
const password = ref("admin123");
const router = useRouter();
const route = useRoute();
const auth = useAdminAuthStore();

onMounted(() => {
  const q = route.query.session;
  if (q === "expired" || q === "error") {
    toast.info("Сессия истекла или требуется повторный вход. Введите логин и пароль.", { duration: 8000 });
    void router.replace({ query: {}, replace: true });
  }
});

const submit = async () => {
  try {
    await auth.login(login.value, password.value);
    toast.success("Успешный вход");
    router.push({ name: "admin-students" });
  } catch {
    toast.error("Неверный логин или пароль");
  }
};
</script>

<template>
  <div class="flex min-h-[70vh] items-center justify-center px-4">
    <div class="w-full max-w-md rounded-2xl border border-pastel-lavender bg-white p-6 shadow-soft">
      <h1 class="mb-6 text-2xl font-semibold">Вход администратора</h1>
      <form class="space-y-4" @submit.prevent="submit">
        <input v-model="login" class="w-full rounded-2xl border border-pastel-lavender bg-ivory px-3 py-2" placeholder="Логин" />
        <input v-model="password" type="password" class="w-full rounded-2xl border border-pastel-lavender bg-ivory px-3 py-2" placeholder="Пароль" />
        <button :disabled="auth.loading" class="w-full rounded-2xl border border-pastel-mint bg-ivory px-3 py-2 font-medium hover:bg-pastel-mint/40">
          {{ auth.loading ? "Входим..." : "Войти" }}
        </button>
      </form>
    </div>
  </div>
</template>
