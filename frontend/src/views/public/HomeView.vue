<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Search } from "lucide-vue-next";
import { api } from "../../services/api";
import BarChart from "../../components/charts/BarChart.vue";

const search = ref("");
const stats = ref<any>(null);
const loading = ref(false);

const load = async () => {
  loading.value = true;
  try {
    const { data } = await api.get("/api/public/stats");
    stats.value = data;
  } finally {
    loading.value = false;
  }
};

onMounted(load);
</script>

<template>
  <section class="space-y-8">
    <div
      class="rounded-2xl border border-matte-lilac/60 bg-gradient-to-r from-[#f2eef9] via-[#e9f0f7] to-[#e8f1ec] p-8 shadow-soft"
    >
      <h1 class="mb-4 text-4xl font-semibold">UNI — аналитика трудоустройства выпускников</h1>
      <div class="flex gap-3">
        <input v-model="search" class="w-full rounded-2xl border border-pastel-lavender bg-white p-3" placeholder="Найти вуз..." />
        <router-link :to="`/universities?search=${search}`" class="inline-flex items-center gap-2 rounded-2xl border border-[#c3b1e1] bg-ivory px-4 py-3 font-medium text-[#5e4b7a] hover:bg-pastel-lavender/40">
          <Search class="h-4 w-4" /> Искать
        </router-link>
      </div>
    </div>

    <div v-if="loading">Загрузка...</div>
    <template v-else-if="stats">
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-2xl border border-pastel-lavender bg-white p-4 shadow-soft">Всего вузов: <b>{{ stats.universities_total }}</b></div>
        <div class="rounded-2xl border border-pastel-blue bg-white p-4 shadow-soft">Средняя зарплата: <b>{{ Math.round(stats.avg_salary) }}</b></div>
        <div class="rounded-2xl border border-pastel-mint bg-white p-4 shadow-soft">Трудоустройство: <b>{{ Number(stats.employment_rate).toFixed(1) }}%</b></div>
        <div class="rounded-2xl border border-pastel-rose bg-white p-4 shadow-soft">Выпускники (последний год): <b>{{ stats.graduates_last_year }}</b></div>
      </div>
      <div class="rounded-2xl bg-white p-4 shadow-soft">
        <h2 class="mb-4 text-xl font-semibold">Топ-10 вузов по зарплате</h2>
        <BarChart
          :labels="stats.top_universities_salary.map((x: any) => x.university_name)"
          :data="stats.top_universities_salary.map((x: any) => Number(x.avg_salary))"
        />
      </div>
      <div class="rounded-2xl bg-white p-4 shadow-soft">
        <h2 class="mb-3 text-xl font-semibold">Региональная занятость</h2>
        <div v-for="region in stats.regional_employment" :key="region.region_name" class="mb-3">
          <div class="mb-1 flex justify-between text-sm">
            <span>{{ region.region_name }}</span><span>{{ region.employment_rate }}%</span>
          </div>
          <div class="h-2 rounded bg-ivory-dark">
            <div class="h-2 rounded bg-pastel-mint" :style="{ width: `${region.employment_rate}%` }"></div>
          </div>
        </div>
      </div>
      <div class="rounded-2xl bg-white p-4 shadow-soft">
        <h2 class="mb-3 text-xl font-semibold">Последние статьи</h2>
        <router-link to="/articles" class="rounded-xl border border-pastel-lavender px-3 py-2 text-sm hover:bg-pastel-lavender/40">
          Перейти к статьям
        </router-link>
      </div>
    </template>
  </section>
</template>
