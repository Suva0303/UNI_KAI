<script setup lang="ts">
import type { TooltipItem } from "chart.js";
import { Bar, Doughnut, Line } from "vue-chartjs";
import { computed } from "vue";
import type {
  EmploymentYearPoint,
  IndustrySlice,
  SalaryDynamicPoint,
  UniversityComparisonRow,
  UniversityOption,
} from "../../types/dashboard";
import SearchableSelect, { type SelectOption } from "./SearchableSelect.vue";

const props = defineProps<{
  activeTab: string;
  salaryData: SalaryDynamicPoint[];
  employmentData: EmploymentYearPoint[];
  industryData: IndustrySlice[];
  comparisonRows: UniversityComparisonRow[];
  universities: UniversityOption[];
  loadingCharts: boolean;
  chartsError: string | null;
  loadingComparison: boolean;
  comparisonError: string | null;
}>();

const emit = defineEmits<{
  "update:activeTab": [string];
}>();

const tabs = [
  { id: "salary", label: "Динамика зарплат", class: "bg-pastel-lavender/80" },
  { id: "employment", label: "Количество выпускников", class: "bg-pastel-mint/80" },
  { id: "industry", label: "Отрасли", class: "bg-pastel-blue/80" },
  { id: "compare", label: "Сравнение вузов", class: "bg-pastel-rose/80" },
];

const comparisonSlots = defineModel<(number | null)[]>("comparisonSlots", {
  default: () => [null, null],
});

const MAX_COMPARE_CARDS = 5;

const moneyFmt = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
const pctFmt = (n: number) => `${n.toFixed(1)}%`;

const STEP_SALARY = 25_000;

const salaryYMax = computed(() => {
  const vals = props.salaryData.map((d) => Number(d.avg_salary)).filter((x) => !Number.isNaN(x));
  if (!vals.length) return STEP_SALARY * 6;
  const mx = Math.max(...vals);
  return Math.max(STEP_SALARY, Math.ceil(mx / STEP_SALARY) * STEP_SALARY);
});

const salaryChartData = computed(() => ({
  labels: props.salaryData.map((d) => String(d.year)),
  datasets: [
    {
      label: "Средняя зарплата (₽)",
      data: props.salaryData.map((d) => d.avg_salary),
      borderColor: "#7E9BB8",
      backgroundColor: "rgba(187, 222, 251, 0.45)",
      fill: true,
      tension: 0.3,
      pointRadius: 5,
      pointHoverRadius: 7,
      pointBackgroundColor: "#5C7FA3",
    },
  ],
}));

const salaryOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: true, labels: { color: "#2d2d2d" } },
    tooltip: {
      callbacks: {
        title: (items: TooltipItem<"line">[]) => `Год: ${items[0]?.label ?? ""}`,
        label: (item: TooltipItem<"line">) => {
          const y = item.parsed.y;
          if (y == null) return "";
          return `Средняя зарплата: ${moneyFmt.format(y)} ₽`;
        },
      },
    },
  },
  scales: {
    x: { title: { display: true, text: "Год выпуска" } },
    y: {
      min: 0,
      max: salaryYMax.value,
      title: { display: true, text: "Средняя зарплата (₽), шаг 25 000" },
      ticks: {
        stepSize: STEP_SALARY,
        callback: (v: string | number) => `${moneyFmt.format(Number(v))} ₽`,
      },
    },
  },
}));

const employmentChartData = computed(() => ({
  labels: props.employmentData.map((d) => String(d.year)),
  datasets: [
    {
      label: "Трудоустроены",
      data: props.employmentData.map((d) => d.employed_percent),
      backgroundColor: "#4CAF50",
      stack: "emp",
      borderRadius: { topLeft: 8, topRight: 8, bottomLeft: 0, bottomRight: 0 },
      borderSkipped: false,
    },
    {
      label: "Безработные",
      data: props.employmentData.map((d) => d.unemployed_percent),
      backgroundColor: "#E57373",
      stack: "emp",
      borderRadius: { topLeft: 0, topRight: 0, bottomLeft: 8, bottomRight: 8 },
      borderSkipped: false,
    },
  ],
}));

const employmentOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  datasets: {
    bar: {
      categoryPercentage: 0.72,
      barPercentage: 0.9,
    },
  },
  plugins: {
    legend: { display: true },
    tooltip: {
      callbacks: {
        title: (items: TooltipItem<"bar">[]) => `Год: ${items[0]?.label ?? ""}`,
        label: (ctx: TooltipItem<"bar">) => {
          const y = ctx.parsed.y;
          if (y == null) return "";
          return `${ctx.dataset.label ?? ""}: ${pctFmt(y)}`;
        },
      },
    },
  },
  scales: {
    x: {
      stacked: true,
      grid: { offset: true },
      ticks: { maxRotation: 0 },
    },
    y: {
      stacked: true,
      min: 0,
      max: 100,
      ticks: {
        callback: (v: string | number) => `${v}%`,
      },
      title: { display: true, text: "Доля, %" },
    },
  },
}));

const pastelPie = ["#E6E6FA", "#B2DFDB", "#FFDAB9", "#BBDEFB", "#F8BBD0", "#C8E6C9", "#B3E5FC"];

const industryChartData = computed(() => ({
  labels: props.industryData.map((d) => d.industry_name),
  datasets: [
    {
      data: props.industryData.map((d) => d.percentage),
      backgroundColor: props.industryData.map((_, i) => pastelPie[i % pastelPie.length]),
      borderWidth: 2,
      borderColor: "#fff",
      hoverOffset: 8,
    },
  ],
}));

const industryOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  cutout: "55%",
  plugins: {
    legend: {
      position: "right" as const,
      labels: { boxWidth: 14, color: "#2d2d2d" },
    },
    tooltip: {
      callbacks: {
        label: (item: TooltipItem<"doughnut">) => {
          const row = props.industryData[item.dataIndex];
          const raw = item.parsed;
          const pct = typeof raw === "number" ? raw : Number((raw as { x?: number; y?: number }).x ?? (raw as { y?: number }).y ?? 0);
          return `${item.label}: ${pct.toFixed(1)}% (${row?.count ?? 0} чел.)`;
        },
      },
    },
  },
}));

const cardShellClass = [
  "border-[#c4b8e8] bg-gradient-to-br from-pastel-lavender/90 via-[#faf8ff] to-white shadow-[0_8px_24px_rgba(198,184,232,0.35)]",
  "border-[#8fc9bf] bg-gradient-to-br from-pastel-mint/90 via-[#f2fbfa] to-white shadow-[0_8px_24px_rgba(143,201,191,0.35)]",
  "border-[#e8b896] bg-gradient-to-br from-pastel-peach/90 via-[#fffaf5] to-white shadow-[0_8px_24px_rgba(232,184,150,0.35)]",
  "border-[#9bbfe0] bg-gradient-to-br from-pastel-blue/90 via-[#f5f9ff] to-white shadow-[0_8px_24px_rgba(155,191,224,0.35)]",
  "border-[#e0a8bc] bg-gradient-to-br from-pastel-rose/90 via-[#fff8fb] to-white shadow-[0_8px_24px_rgba(224,168,188,0.35)]",
];

const cardSelectBorder = [
  "border-pastel-lavender",
  "border-pastel-mint",
  "border-pastel-peach",
  "border-pastel-blue",
  "border-pastel-rose",
];

function optionsForSlot(slotIndex: number): SelectOption[] {
  const slots = comparisonSlots.value;
  const taken = new Set(
    slots
      .map((id, i) => (i !== slotIndex && id != null ? id : null))
      .filter((x): x is number => x != null),
  );
  return [
    { value: null, label: "Выберите вуз…" },
    ...props.universities
      .filter((u) => !taken.has(u.university_id))
      .map((u) => ({
        value: u.university_id,
        label: [u.university_name, u.city_name ? `(${u.city_name})` : null].filter(Boolean).join(" "),
      })),
  ];
}

function setSlotUniversity(slotIndex: number, value: string | number | null) {
  const next = [...comparisonSlots.value];
  next[slotIndex] = value === null || value === "" ? null : Number(value);
  comparisonSlots.value = next;
}

function rowForUniversity(id: number | null): UniversityComparisonRow | null {
  if (id == null) return null;
  return props.comparisonRows.find((r) => r.university_id === id) ?? null;
}

function addCompareCard() {
  if (comparisonSlots.value.length >= MAX_COMPARE_CARDS) return;
  comparisonSlots.value = [...comparisonSlots.value, null];
}
</script>

<template>
  <div class="rounded-2xl border border-charcoal/5 bg-white p-4 shadow-soft">
    <p v-if="chartsError && activeTab !== 'compare'" class="mb-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      {{ chartsError }}
    </p>

    <div class="-mx-1 flex gap-2 overflow-x-auto pb-2 scrollbar-thin">
      <button
        v-for="t in tabs"
        :key="t.id"
        type="button"
        class="shrink-0 rounded-full px-4 py-2 text-sm font-medium transition"
        :class="activeTab === t.id ? t.class + ' ring-2 ring-charcoal/20' : 'bg-ivory text-charcoal/80 hover:bg-ivory-dark'"
        @click="emit('update:activeTab', t.id)"
      >
        {{ t.label }}
      </button>
    </div>

    <div class="relative mt-4 min-h-[320px]">
      <div v-if="loadingCharts && activeTab !== 'compare'" class="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-white/70">
        <div class="h-10 w-10 animate-spin rounded-full border-2 border-pastel-blue border-t-transparent" aria-hidden="true" />
        <span class="sr-only">Загрузка графиков</span>
      </div>

      <div v-if="activeTab === 'salary'" class="h-80">
        <Line v-if="salaryData.length" :data="salaryChartData" :options="salaryOptions" />
        <p v-else class="py-12 text-center text-sm text-charcoal/60">Нет данных для выбранных фильтров</p>
      </div>

      <div v-else-if="activeTab === 'employment'" class="h-80">
        <Bar v-if="employmentData.length" :data="employmentChartData" :options="employmentOptions" />
        <p v-else class="py-12 text-center text-sm text-charcoal/60">Нет данных для выбранных фильтров</p>
      </div>

      <div v-else-if="activeTab === 'industry'" class="mx-auto h-96 max-w-3xl">
        <Doughnut v-if="industryData.length" :data="industryChartData" :options="industryOptions" />
        <p v-else class="py-12 text-center text-sm text-charcoal/60">Нет данных для выбранных фильтров</p>
      </div>

      <div v-else class="space-y-4">
        <p v-if="comparisonError" class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {{ comparisonError }}
        </p>

        <div v-if="loadingComparison" class="flex justify-center py-10">
          <div class="h-10 w-10 animate-spin rounded-full border-2 border-pastel-rose border-t-transparent" />
        </div>

        <div v-else class="flex flex-wrap items-stretch justify-center gap-4">
          <div
            v-for="(_slot, idx) in comparisonSlots"
            :key="idx"
            class="relative flex w-full min-w-[240px] max-w-sm flex-1 flex-col gap-3 rounded-2xl border-2 p-4 transition hover:-translate-y-0.5"
            :class="cardShellClass[idx % cardShellClass.length]"
          >
            <div class="flex items-start justify-between gap-2 border-b border-charcoal/10 pb-2">
              <span class="text-xs font-semibold uppercase tracking-wide text-charcoal/50"></span>
            </div>
            <SearchableSelect
              :model-value="comparisonSlots[idx] ?? null"
              :options="optionsForSlot(idx)"
              placeholder="Выберите вуз…"
              :border-class="cardSelectBorder[idx % cardSelectBorder.length]"
              @update:model-value="setSlotUniversity(idx, $event)"
            />

            <template v-if="comparisonSlots[idx] != null">
              <template v-if="rowForUniversity(comparisonSlots[idx]!)">
                <div class="space-y-2 rounded-xl bg-white/65 px-3 py-3 text-sm shadow-inner backdrop-blur-sm">
                  <div class="flex justify-between gap-2 border-b border-charcoal/5 pb-2">
                    <span class="text-charcoal/65">Общий % трудоустройства</span>
                    <span class="font-semibold tabular-nums text-charcoal">{{
                      pctFmt(rowForUniversity(comparisonSlots[idx]!)!.employment_total_percent)
                    }}</span>
                  </div>
                  <div class="flex justify-between gap-2 border-b border-charcoal/5 pb-2">
                    <span class="text-charcoal/65">По специальности</span>
                    <span class="font-semibold tabular-nums text-charcoal">{{
                      pctFmt(rowForUniversity(comparisonSlots[idx]!)!.employment_specialty_percent)
                    }}</span>
                  </div>
                  <div class="flex justify-between gap-2 border-b border-charcoal/5 pb-2">
                    <span class="text-charcoal/65">Выпускников</span>
                    <span class="font-semibold tabular-nums text-charcoal">{{
                      moneyFmt.format(rowForUniversity(comparisonSlots[idx]!)!.graduates_count)
                    }}</span>
                  </div>
                  <div class="flex justify-between gap-2">
                    <span class="text-charcoal/65">Средняя зарплата</span>
                    <span class="font-semibold tabular-nums text-charcoal">
                      {{ moneyFmt.format(rowForUniversity(comparisonSlots[idx]!)!.avg_salary) }} ₽
                    </span>
                  </div>
                </div>
                <p class="text-center text-xs font-medium leading-tight text-charcoal/70">
                  {{ rowForUniversity(comparisonSlots[idx]!)!.university_name }}
                </p>
              </template>
              <p v-else class="rounded-lg bg-white/50 px-2 py-4 text-center text-xs text-charcoal/60">
                Нет данных по витрине для выбранного вуза и текущих фильтров.
              </p>
            </template>
            <p v-else class="flex flex-1 items-center justify-center rounded-lg border border-dashed border-charcoal/15 bg-white/40 px-2 py-6 text-center text-xs text-charcoal/55">
              Выберите вуз в списке выше
            </p>
          </div>

          <button
            v-if="comparisonSlots.length < MAX_COMPARE_CARDS"
            type="button"
            class="group flex h-[min(120px,100%)] min-h-[200px] w-[88px] shrink-0 flex-col items-center justify-center rounded-2xl border-2 border-dashed border-charcoal/20 bg-gradient-to-b from-ivory via-pastel-lavender/30 to-pastel-blue/25 text-charcoal/40 shadow-inner transition [transform:perspective(420px)_rotateY(-12deg)] hover:border-pastel-rose/60 hover:from-pastel-rose/20 hover:to-pastel-mint/25 hover:text-charcoal hover:[transform:perspective(420px)_rotateY(0deg)_scale(1.04)] focus:outline-none focus-visible:ring-2 focus-visible:ring-pastel-rose/50"
            aria-label="Добавить карточку вуза"
            @click="addCompareCard"
          >
            <span
              class="select-none text-5xl font-extralight leading-none text-transparent drop-shadow-[0_4px_0_rgba(45,45,45,0.12)] [background:linear-gradient(165deg,#8b7fd8,#e879a9,#7ec8e3)] [-webkit-background-clip:text] [background-clip:text]"
            >+</span>
            <span
              class="mt-2 max-w-[4.5rem] text-center text-[10px] font-medium uppercase leading-tight tracking-wide text-charcoal/45 group-hover:text-charcoal/70"
            >Добавить</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
