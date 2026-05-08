<script setup lang="ts">
import { Building2, CirclePercent, Coins, Users } from "lucide-vue-next";
import { computed } from "vue";
import type { DashboardKpis } from "../../types/dashboard";

const props = defineProps<{
  kpis: DashboardKpis | null;
  loading: boolean;
  error: string | null;
}>();

const moneyFmt = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});

const intFmt = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });

const cards = computed(() => {
  const k = props.kpis;
  if (!k) {
    return [
      { key: "salary", label: "Средняя зарплата выпускников", value: "—", border: "border-pastel-blue", icon: Coins },
      { key: "emp", label: "Процент трудоустройства", value: "—", border: "border-pastel-mint", icon: CirclePercent },
      { key: "grad", label: "Количество выпускников", value: "—", border: "border-pastel-lavender", icon: Users },
      { key: "top", label: "Топ работодатель", value: "—", border: "border-pastel-rose", icon: Building2 },
    ];
  }
  return [
    {
      key: "salary",
      label: "Средняя зарплата выпускников",
      value: moneyFmt.format(k.avg_salary),
      border: "border-pastel-blue",
      icon: Coins,
    },
    {
      key: "emp",
      label: "Процент трудоустройства",
      value: `${k.employment_rate.toFixed(1)}%`,
      border: "border-pastel-mint",
      icon: CirclePercent,
    },
    {
      key: "grad",
      label: "Количество выпускников",
      value: intFmt.format(k.graduates_count),
      border: "border-pastel-lavender",
      icon: Users,
    },
    {
      key: "top",
      label: "Топ работодатель",
      value: k.top_employer && k.top_employer.trim() !== "" ? k.top_employer : "Нет данных",
      border: "border-pastel-rose",
      icon: Building2,
    },
  ];
});
</script>

<template>
  <div class="space-y-3">
    <p v-if="error" class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{{ error }}</p>
    <div v-if="loading" class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <div v-for="i in 4" :key="i" class="h-28 animate-pulse rounded-2xl bg-charcoal/5" />
    </div>
    <div v-else class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <article
        v-for="c in cards"
        :key="c.key"
        class="flex gap-3 rounded-2xl border-2 bg-white p-4 shadow-soft"
        :class="c.border"
      >
        <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-ivory">
          <component :is="c.icon" class="h-5 w-5 text-charcoal/80" />
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-xs font-medium text-charcoal/65">{{ c.label }}</p>
          <p class="mt-1 break-words text-xl font-semibold leading-tight text-charcoal">{{ c.value }}</p>
        </div>
      </article>
    </div>
  </div>
</template>
