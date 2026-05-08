<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../../services/api";

const stats = ref<any>(null);
const loading = ref(false);

const load = async () => {
  loading.value = true;
  try {
    const { data } = await api.get("/api/admin/dashboard/stats");
    stats.value = data;
  } finally {
    loading.value = false;
  }
};

onMounted(load);
</script>

<template>
  <section>
    <h1 class="mb-6 text-3xl font-semibold text-charcoal">Админ-дашборд</h1>
    <div v-if="loading">Загрузка...</div>
    <div v-else-if="stats" class="space-y-6">
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-2xl border border-matte-blue/80 bg-white p-4 shadow-sm">
          Всего вузов: <b>{{ stats.universities_total }}</b>
        </div>
        <div class="rounded-2xl border border-matte-sage/80 bg-white p-4 shadow-sm">
          Всего выпускников: <b>{{ stats.graduates_total }}</b>
        </div>
        <div class="rounded-2xl border border-matte-lilac/80 bg-white p-4 shadow-sm">
          Всего компаний: <b>{{ stats.companies_total }}</b>
        </div>
        <div class="rounded-2xl border border-pastel-rose/50 bg-white p-4 shadow-sm">
          Трудоустроек: <b>{{ stats.employments_total }}</b>
        </div>
      </div>
      <div class="rounded-2xl border border-matte-lilac/80 bg-white p-4 shadow-sm">
        <h2 class="mb-3 text-xl font-semibold">Последние события импорта</h2>
        <table class="w-full text-left text-sm">
          <thead>
            <tr class="text-charcoal/50">
              <th>Task</th>
              <th>Дата</th>
              <th>Строк</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in stats.last_events" :key="event.task_id" class="border-t border-matte-lilac/80">
              <td>{{ event.task_id }}</td>
              <td>{{ event.load_timestamp }}</td>
              <td>{{ event.row_count }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>
