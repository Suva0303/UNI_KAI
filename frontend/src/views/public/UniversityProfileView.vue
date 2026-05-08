<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ArrowLeft, Banknote, Briefcase, GraduationCap, MapPin, Target } from "lucide-vue-next";
import { Bar, Doughnut, Line } from "vue-chartjs";
import { api } from "../../services/api";
import BarChart from "../../components/charts/BarChart.vue";
import type { IndustrySlice, ProgramAnalyticsRow, ProgramEmployerRow, SalaryDynamicPoint, UniversityProfile } from "../../types/dashboard";

const route = useRoute();
const id = computed(() => Number(route.params.id));

const profile = ref<UniversityProfile | null>(null);
const salarySeries = ref<SalaryDynamicPoint[]>([]);
const industries = ref<IndustrySlice[]>([]);
const programsCatalog = ref<{ program_code: string; program_name: string }[]>([]);
const programAnalytics = ref<ProgramAnalyticsRow[]>([]);
const employers = ref<ProgramEmployerRow[]>([]);
const programCodeA = ref<string>("");
const programCodeB = ref<string>("");
const showSecondProgram = ref(false);
const graduationYearStr = ref<string>("");
const loadingPrograms = ref(false);
const loadingCharts = ref(false);
const loading = ref(true);
const error = ref<string | null>(null);

let filterRequestGen = 0;
let programCompareGen = 0;

const viewportMdUp = ref(true);
function updateViewport() {
  viewportMdUp.value = typeof window !== "undefined" && window.matchMedia("(min-width: 768px)").matches;
}

function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const d = err.response?.data as { detail?: unknown } | undefined;
    const detail = d?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0] && typeof (detail[0] as { msg?: string }).msg === "string") {
      return (detail[0] as { msg: string }).msg;
    }
    if (err.response?.status === 404) return "Запрошенный ресурс не найден (404).";
    return err.message || "Ошибка запроса";
  }
  return "Ошибка загрузки";
}

const moneyFmt = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
const pctFmt = (n: number) => `${n.toFixed(1)}%`;

const SALARY_Y_FIXED = [0, 25_000, 50_000, 100_000, 125_000, 150_000];

function buildGraduateAxis(maxVal: number): { max: number; ticks: number[] } {
  const m = Math.max(0, maxVal);
  if (m <= 10) return { max: 50, ticks: [0, 5, 10, 25, 50] };
  if (m <= 50) return { max: 100, ticks: [0, 10, 25, 50, 100] };
  if (m <= 500) return { max: 500, ticks: [0, 50, 100, 250, 500] };
  if (m <= 10000) return { max: 10000, ticks: [0, 250, 500, 1000, 2500, 5000, 10000] };
  const cap = Math.ceil((m * 1.08) / 5000) * 5000;
  const ticks: number[] = [0, 250, 500, 1000, 2500, 5000, 10000];
  for (let v = 15000; v < cap; v += 5000) ticks.push(v);
  ticks.push(cap);
  return { max: cap, ticks: [...new Set(ticks)].sort((a, b) => a - b) };
}

const employerXAxis = computed(() =>
  buildGraduateAxis(Math.max(0, ...employers.value.map((e) => e.graduates_count))),
);

const lineData = computed(() => ({
  labels: salarySeries.value.map((d) => String(d.year)),
  datasets: [
    {
      label: "Средняя зарплата (₽)",
      data: salarySeries.value.map((d) => d.avg_salary),
      borderColor: "#5C7FA3",
      backgroundColor: "rgba(187, 222, 251, 0.4)",
      fill: true,
      tension: 0.3,
      pointRadius: 4,
    },
  ],
}));

const lineOptions = computed(() => {
  const vals = salarySeries.value.map((d) => Number(d.avg_salary)).filter((x) => !Number.isNaN(x));
  const dataMax = vals.length ? Math.max(...vals) : 0;
  const cap = Math.max(150_000, Math.ceil(dataMax / 25_000) * 25_000);
  let tickList: number[];
  if (cap <= 150_000) {
    tickList = SALARY_Y_FIXED;
  } else {
    tickList = [0];
    const step = cap > 500_000 ? 100_000 : 50_000;
    for (let v = step; v < cap; v += step) tickList.push(v);
    tickList.push(cap);
  }
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index" as const, intersect: false },
    plugins: {
      legend: { display: true, labels: { color: "#2d2d2d", font: { size: 12 } } },
    },
    scales: {
      x: {
        title: { display: true, text: "Год выпуска", color: "#2d2d2d", font: { size: 12 } },
        ticks: { color: "#5a5a5a", maxRotation: 45 },
        grid: { color: "rgba(45,45,45,0.06)" },
      },
      y: {
        min: 0,
        max: cap <= 150_000 ? 150_000 : cap,
        title: { display: true, text: "Зарплата, ₽", color: "#2d2d2d", font: { size: 12 } },
        afterBuildTicks: (scale: { ticks: { value: number }[] }) => {
          scale.ticks = tickList.map((v) => ({ value: v })) as { value: number }[];
        },
        ticks: {
          color: "#5a5a5a",
          callback: (v: number | string) => moneyFmt.format(Number(v)),
        },
        grid: { color: "rgba(45,45,45,0.06)" },
      },
    },
  };
});

const pastel = [
  "#C5D4E8",
  "#B8D4C8",
  "#E8D4B8",
  "#D4C8E8",
  "#E8C8D0",
  "#C8E0E8",
  "#D4E8E0",
  "#E0D4E8",
  "#E8E0D4",
  "#B8C8E8",
  "#C8E8D8",
  "#E8D8C8",
  "#D8C8E8",
  "#C8D8E8",
  "#E8C8B8",
];

const doughnutData = computed(() => ({
  labels: industries.value.map((d) => d.industry_name),
  datasets: [
    {
      data: industries.value.map((d) => d.percentage),
      backgroundColor: industries.value.map((_, i) => pastel[i % pastel.length]),
      borderWidth: 2,
      borderColor: "#fff",
      hoverOffset: 6,
    },
  ],
}));

const doughnutOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  cutout: "58%",
  plugins: {
    legend: {
      position: (viewportMdUp.value ? "right" : "bottom") as "right" | "bottom",
      labels: {
        boxWidth: 12,
        color: "#2d2d2d",
        font: { size: viewportMdUp.value ? 11 : 10 },
        padding: viewportMdUp.value ? 10 : 8,
      },
    },
    tooltip: {
      callbacks: {
        label: (item: { label: string; parsed: number; dataIndex: number }) => {
          const row = industries.value[item.dataIndex];
          return `${item.label}: ${item.parsed.toFixed(1)}% (${row?.count ?? 0})`;
        },
      },
    },
  },
}));

const gradYearsForFilter = ref<number[]>([]);

function graduationYearParam(): number | undefined {
  const y = Number(graduationYearStr.value);
  return Number.isFinite(y) && graduationYearStr.value !== "" ? y : undefined;
}

function addSecondProgram() {
  showSecondProgram.value = true;
  if (!programCodeB.value.trim()) {
    const alt = programsCatalog.value.find((x) => x.program_code !== programCodeA.value);
    programCodeB.value = alt?.program_code ?? programsCatalog.value[0]?.program_code ?? "";
  }
}

function removeSecondProgram() {
  showSecondProgram.value = false;
  programCodeB.value = "";
}

function chartFilterParams(): Record<string, string | number> {
  const p: Record<string, string | number> = {};
  if (programCodeA.value.trim()) p.program_code = programCodeA.value.trim();
  const gy = graduationYearParam();
  if (gy !== undefined) p.graduation_year = gy;
  return p;
}

function profileFilterParams(): Record<string, string | number> {
  return chartFilterParams();
}

async function loadGraduationYearOptions() {
  const uid = id.value;
  if (!Number.isFinite(uid)) return;
  try {
    const params: Record<string, string> = {};
    if (programCodeA.value.trim()) params.program_code = programCodeA.value.trim();
    const { data } = await api.get<SalaryDynamicPoint[]>(`/api/public/universities/${uid}/salary-dynamics`, { params });
    const ys = new Set<number>();
    for (const x of data ?? []) {
      const y = Number(x.year);
      if (Number.isFinite(y)) ys.add(y);
    }
    gradYearsForFilter.value = [...ys].sort((a, b) => b - a);
    const sel = Number(graduationYearStr.value);
    if (graduationYearStr.value !== "" && !gradYearsForFilter.value.includes(sel)) {
      graduationYearStr.value = "";
    }
  } catch {
    gradYearsForFilter.value = [];
  }
}

async function syncDashboardWidgets(gen: number) {
  const uid = id.value;
  if (!Number.isFinite(uid)) return;
  loadingCharts.value = true;
  try {
    const params = chartFilterParams();
    const profP =
      profile.value != null
        ? api.get<UniversityProfile>(`/api/public/universities/${uid}/profile`, { params: profileFilterParams() })
        : Promise.resolve({ data: null as UniversityProfile | null });
    const [s, ind, emp, profRes] = await Promise.all([
      api.get<SalaryDynamicPoint[]>(`/api/public/universities/${uid}/salary-dynamics`, { params }),
      api.get<IndustrySlice[]>(`/api/public/universities/${uid}/industries`, { params }),
      api.get<ProgramEmployerRow[]>(`/api/public/universities/${uid}/employers`, { params }),
      profP,
    ]);
    if (gen !== filterRequestGen) return;
    salarySeries.value = (s.data ?? []).map((x) => ({ year: Number(x.year), avg_salary: Number(x.avg_salary) }));
    industries.value = (ind.data ?? []).map((x) => ({
      industry_name: String(x.industry_name),
      count: Number(x.count),
      percentage: Number(x.percentage),
    }));
    employers.value = (emp.data ?? []).map((x) => ({
      company_name: String(x.company_name),
      graduates_count: Number(x.graduates_count ?? 0),
    }));
    const data = profRes.data;
    if (profile.value && data) {
      profile.value = {
        ...profile.value,
        graduates_count: Number(data.graduates_count ?? 0),
        avg_salary: Number(data.avg_salary ?? 0),
        employment_rate: Number(data.employment_rate ?? 0),
        specialty_rate: Number(data.specialty_rate ?? 0),
      };
    }
  } catch {
    if (gen !== filterRequestGen) return;
    salarySeries.value = [];
    industries.value = [];
    employers.value = [];
  } finally {
    if (gen === filterRequestGen) loadingCharts.value = false;
  }
}

async function onAnalyticsFiltersChanged() {
  const gen = ++filterRequestGen;
  await syncDashboardWidgets(gen);
  if (gen !== filterRequestGen) return;
  await loadProgramAnalytics(gen);
}

function programLineData(row: ProgramAnalyticsRow) {
  return {
    labels: row.salary_by_year.map((d) => String(d.year)),
    datasets: [
      {
        label: "Средняя зарплата (₽)",
        data: row.salary_by_year.map((d) => d.avg_salary),
        borderColor: "#5C7FA3",
        backgroundColor: "rgba(187, 222, 251, 0.35)",
        fill: true,
        tension: 0.25,
        pointRadius: 3,
      },
    ],
  };
}

const programLineOptionsShort = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false } },
  scales: {
    x: { title: { display: true, text: "Год выпуска" }, ticks: { maxRotation: 45, font: { size: 10 } } },
    y: { beginAtZero: true, title: { display: true, text: "Зарплата, ₽" } },
  },
};

async function loadProgramAnalytics(gen: number) {
  const uid = id.value;
  if (!Number.isFinite(uid)) return;
  const codes = [programCodeA.value, showSecondProgram.value ? programCodeB.value : ""].map((c) => c.trim()).filter(Boolean);
  if (!codes.length) {
    if (gen === filterRequestGen) programAnalytics.value = [];
    return;
  }
  loadingPrograms.value = true;
  try {
    const gy = graduationYearParam();
    const { data } = await api.get<ProgramAnalyticsRow[]>(`/api/public/universities/${uid}/program-analytics`, {
      params: {
        program_code: codes,
        ...(gy !== undefined ? { graduation_year: gy } : {}),
      },
    });
    if (gen !== filterRequestGen) return;
    programAnalytics.value = (data ?? []).map((r) => ({
      program_code: String(r.program_code),
      program_name: String(r.program_name),
      avg_salary: Number(r.avg_salary ?? 0),
      employment_rate: Number(r.employment_rate ?? 0),
      specialty_rate: Number(r.specialty_rate ?? 0),
      salary_by_year: (r.salary_by_year ?? []).map((x) => ({ year: Number(x.year), avg_salary: Number(x.avg_salary) })),
    }));
  } catch {
    if (gen !== filterRequestGen) return;
    programAnalytics.value = [];
  } finally {
    if (gen === filterRequestGen) loadingPrograms.value = false;
  }
}

async function loadProgramAnalyticsCompareOnly() {
  const gen = ++programCompareGen;
  const uid = id.value;
  if (!Number.isFinite(uid)) return;
  const codes = [programCodeA.value, showSecondProgram.value ? programCodeB.value : ""].map((c) => c.trim()).filter(Boolean);
  if (!codes.length) {
    if (gen === programCompareGen) programAnalytics.value = [];
    return;
  }
  loadingPrograms.value = true;
  try {
    const gy = graduationYearParam();
    const { data } = await api.get<ProgramAnalyticsRow[]>(`/api/public/universities/${uid}/program-analytics`, {
      params: {
        program_code: codes,
        ...(gy !== undefined ? { graduation_year: gy } : {}),
      },
    });
    if (gen !== programCompareGen) return;
    programAnalytics.value = (data ?? []).map((r) => ({
      program_code: String(r.program_code),
      program_name: String(r.program_name),
      avg_salary: Number(r.avg_salary ?? 0),
      employment_rate: Number(r.employment_rate ?? 0),
      specialty_rate: Number(r.specialty_rate ?? 0),
      salary_by_year: (r.salary_by_year ?? []).map((x) => ({ year: Number(x.year), avg_salary: Number(x.avg_salary) })),
    }));
  } catch {
    if (gen !== programCompareGen) return;
    programAnalytics.value = [];
  } finally {
    if (gen === programCompareGen) loadingPrograms.value = false;
  }
}

async function loadUniversityPage() {
  const uid = id.value;
  if (!Number.isFinite(uid)) {
    error.value = "Некорректный идентификатор.";
    loading.value = false;
    return;
  }
  loading.value = true;
  error.value = null;
  try {
    const [p, prog] = await Promise.all([
      api.get<UniversityProfile>(`/api/public/universities/${uid}/profile`),
      api.get<{ program_code: string; program_name: string }[]>(`/api/public/programs`),
    ]);
    profile.value = {
      ...p.data,
      logo_url: p.data.logo_url ? String(p.data.logo_url) : null,
      graduates_count: Number(p.data.graduates_count ?? 0),
      avg_salary: Number(p.data.avg_salary ?? 0),
      employment_rate: Number(p.data.employment_rate ?? 0),
      specialty_rate: Number(p.data.specialty_rate ?? 0),
    };
    programsCatalog.value = prog.data ?? [];
    programCodeA.value = "";
    programCodeB.value = "";
    showSecondProgram.value = false;
    graduationYearStr.value = "";
    await loadGraduationYearOptions();
    await onAnalyticsFiltersChanged();
  } catch (e) {
    error.value = formatApiError(e);
    profile.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  updateViewport();
  window.addEventListener("resize", updateViewport);
  await loadUniversityPage();
});

onUnmounted(() => {
  window.removeEventListener("resize", updateViewport);
});

watch(id, (newId, oldId) => {
  if (!Number.isFinite(newId)) return;
  if (oldId !== undefined && newId === oldId) return;
  void loadUniversityPage();
});

watch(
  () => programCodeA.value,
  async () => {
    await loadGraduationYearOptions();
    await onAnalyticsFiltersChanged();
  },
);

watch(() => graduationYearStr.value, async () => {
  await onAnalyticsFiltersChanged();
});

watch([() => programCodeB.value, () => showSecondProgram.value], () => {
  void loadProgramAnalyticsCompareOnly();
});
</script>

<template>
  <section class="space-y-6">
    <router-link
      to="/universities"
      class="inline-flex items-center gap-2 rounded-xl border border-charcoal/10 bg-white px-3 py-2 text-sm text-charcoal/80 shadow-sm transition hover:border-pastel-blue hover:text-charcoal"
    >
      <ArrowLeft class="h-4 w-4 shrink-0" stroke-width="2" />
      Назад к списку
    </router-link>

    <p v-if="loading" class="text-sm text-charcoal/60">Загрузка…</p>
    <p v-else-if="error" class="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{{ error }}</p>

    <template v-else-if="profile">
      <div class="flex flex-col gap-4 rounded-2xl border border-charcoal/10 bg-white p-5 shadow-soft md:flex-row md:items-start">
        <div
          class="relative flex h-32 w-32 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-charcoal/10 bg-charcoal/[0.04] text-charcoal/35 sm:h-36 sm:w-36 md:h-40 md:w-40"
        >
          <img
            v-if="profile.logo_url && profile.logo_url.trim()"
            :src="profile.logo_url.trim()"
            :alt="profile.university_name"
            class="h-full w-full object-cover"
            loading="lazy"
            decoding="async"
          />
          <GraduationCap v-else class="h-16 w-16 sm:h-[4.25rem] sm:w-[4.25rem] md:h-[4.5rem] md:w-[4.5rem]" stroke-width="1.25" aria-hidden="true" />
        </div>
        <div class="min-w-0 flex-1 space-y-3">
          <h1 class="text-2xl font-semibold leading-tight text-charcoal md:text-3xl">{{ profile.university_name }}</h1>
          <div class="flex flex-wrap gap-x-4 gap-y-2 text-sm text-charcoal/75">
            <span v-if="profile.region_name" class="inline-flex items-center gap-1">
              <MapPin class="h-4 w-4 text-charcoal/45" stroke-width="2" />
              {{ profile.region_name }}
            </span>
            <span v-if="profile.foundation_year">Основан: {{ profile.foundation_year }}</span>
            <a
              v-if="profile.website"
              :href="profile.website.startsWith('http') ? profile.website : `https://${profile.website}`"
              target="_blank"
              rel="noopener noreferrer"
              class="text-pastel-blue underline decoration-charcoal/20 underline-offset-2 hover:decoration-pastel-blue"
            >
              Сайт вуза
            </a>
          </div>
          <p v-if="profile.description" class="max-w-3xl text-sm leading-relaxed text-charcoal/80">{{ profile.description }}</p>
        </div>
      </div>

      <div class="grid grid-cols-2 gap-2 sm:gap-3 lg:grid-cols-4">
        <div
          class="flex min-h-0 items-center gap-2.5 rounded-xl border border-charcoal/10 bg-white px-2.5 py-2 shadow-sm sm:gap-3 sm:px-3 sm:py-2.5"
        >
          <Banknote class="h-10 w-10 shrink-0 text-charcoal/35 sm:h-11 sm:w-11" stroke-width="1.5" />
          <div class="min-w-0 leading-tight">
            <p class="text-[10px] font-medium text-charcoal/55 sm:text-[11px]">Средняя ЗП</p>
            <p class="text-sm font-semibold tabular-nums text-charcoal sm:text-base">{{ moneyFmt.format(profile.avg_salary) }} ₽</p>
          </div>
        </div>
        <div
          class="flex min-h-0 items-center gap-2.5 rounded-xl border border-charcoal/10 bg-white px-2.5 py-2 shadow-sm sm:gap-3 sm:px-3 sm:py-2.5"
        >
          <Briefcase class="h-10 w-10 shrink-0 text-charcoal/35 sm:h-11 sm:w-11" stroke-width="1.5" />
          <div class="min-w-0 leading-tight">
            <p class="text-[10px] font-medium text-charcoal/55 sm:text-[11px]">Трудоустройство</p>
            <p class="text-sm font-semibold tabular-nums text-charcoal sm:text-base">{{ pctFmt(profile.employment_rate) }}</p>
          </div>
        </div>
        <div
          class="flex min-h-0 items-center gap-2.5 rounded-xl border border-charcoal/10 bg-white px-2.5 py-2 shadow-sm sm:gap-3 sm:px-3 sm:py-2.5"
        >
          <Target class="h-10 w-10 shrink-0 text-charcoal/35 sm:h-11 sm:w-11" stroke-width="1.5" />
          <div class="min-w-0 leading-tight">
            <p class="text-[10px] font-medium text-charcoal/55 sm:text-[11px]">По специальности</p>
            <p class="text-sm font-semibold tabular-nums text-charcoal sm:text-base">{{ pctFmt(profile.specialty_rate) }}</p>
          </div>
        </div>
        <div
          class="flex min-h-0 items-center gap-2.5 rounded-xl border border-charcoal/10 bg-white px-2.5 py-2 shadow-sm sm:gap-3 sm:px-3 sm:py-2.5"
        >
          <GraduationCap class="h-10 w-10 shrink-0 text-charcoal/35 sm:h-11 sm:w-11" stroke-width="1.5" />
          <div class="min-w-0 leading-tight">
            <p class="text-[10px] font-medium text-charcoal/55 sm:text-[11px]">Выпускников</p>
            <p class="text-sm font-semibold tabular-nums text-charcoal sm:text-base">{{ moneyFmt.format(profile.graduates_count) }}</p>
          </div>
        </div>
      </div>

      <section class="space-y-4 rounded-2xl border border-charcoal/10 bg-white p-4 shadow-sm sm:p-5">
        <h2 class="text-base font-semibold text-charcoal">Аналитика по направлениям подготовки</h2>
        <div class="flex flex-wrap items-end gap-3">
          <label class="flex min-w-[220px] flex-1 flex-col gap-1">
            <span class="text-xs font-medium text-charcoal/65">Направление подготовки</span>
            <select
              v-model="programCodeA"
              class="min-h-11 w-full rounded-xl border border-pastel-blue/70 bg-white px-3 py-2.5 text-sm text-charcoal shadow-sm"
            >
              <option value="">Все направления</option>
              <option v-for="pr in programsCatalog" :key="pr.program_code" :value="pr.program_code">
                {{ pr.program_name }} ({{ pr.program_code }})
              </option>
            </select>
          </label>
          <label class="flex min-w-[200px] flex-1 flex-col gap-1">
            <span class="text-xs font-medium text-charcoal/65">Год выпуска</span>
            <select
              v-model="graduationYearStr"
              class="min-h-11 rounded-xl border border-pastel-blue/70 bg-white px-3 py-2.5 text-sm text-charcoal shadow-sm"
            >
              <option value="">Все годы</option>
              <option v-for="y in gradYearsForFilter" :key="y" :value="String(y)">{{ y }}</option>
            </select>
          </label>
          <label v-if="showSecondProgram" class="flex min-w-[220px] flex-1 flex-col gap-1">
            <span class="text-xs font-medium text-charcoal/65">Второе направление</span>
            <select v-model="programCodeB" class="min-h-11 rounded-xl border border-pastel-blue/70 bg-white px-3 py-2.5 text-sm text-charcoal shadow-sm">
              <option v-for="pr in programsCatalog" :key="`b-${pr.program_code}`" :value="pr.program_code">
                {{ pr.program_name }} ({{ pr.program_code }})
              </option>
            </select>
          </label>
          <button
            v-if="!showSecondProgram && programsCatalog.length > 1"
            type="button"
            class="min-h-11 rounded-xl border border-charcoal/15 bg-ivory/60 px-4 py-2.5 text-sm text-charcoal shadow-sm transition hover:border-pastel-blue"
            @click="addSecondProgram"
          >
            + Направление
          </button>
          <button
            v-if="showSecondProgram"
            type="button"
            class="min-h-11 rounded-xl border border-charcoal/15 bg-white px-4 py-2.5 text-sm text-charcoal/75 shadow-sm transition hover:border-pastel-blue"
            @click="removeSecondProgram"
          >
            Убрать второе
          </button>
        </div>
        <p v-if="loadingCharts" class="text-xs text-charcoal/55">Обновление графиков…</p>

        <div class="flex flex-col gap-4 min-[960px]:flex-row min-[960px]:items-stretch">
          <div
            class="flex min-h-0 min-w-0 flex-1 flex-col rounded-2xl border border-charcoal/10 bg-ivory/30 p-4 shadow-sm sm:p-5"
          >
            <h3 class="mb-2 shrink-0 text-sm font-semibold text-charcoal md:text-base">Динамика зарплат выпускников</h3>
            <div v-if="salarySeries.length" class="h-64 w-full min-w-0 sm:h-72 md:h-80">
              <Line
                :key="`salary-${programCodeA}-${graduationYearStr}`"
                :data="lineData"
                :options="lineOptions as any"
              />
            </div>
            <p v-else class="flex flex-1 items-center justify-center py-10 text-center text-sm text-charcoal/55">Нет данных для графика.</p>
          </div>
          <div
            class="flex min-h-0 min-w-0 flex-1 flex-col rounded-2xl border border-charcoal/10 bg-ivory/30 p-4 shadow-sm sm:p-5"
          >
            <h3 class="mb-2 shrink-0 text-sm font-semibold text-charcoal md:text-base">Распределение по отраслям</h3>
            <div v-if="industries.length" class="h-64 w-full min-w-0 sm:h-72 md:h-80">
              <Doughnut
                :key="`ind-${programCodeA}-${graduationYearStr}`"
                :data="doughnutData"
                :options="doughnutOptions as any"
              />
            </div>
            <p v-else class="flex flex-1 items-center justify-center py-10 text-center text-sm text-charcoal/55">Нет данных по отраслям.</p>
          </div>
        </div>

        <p v-if="loadingPrograms" class="text-sm text-charcoal/55">Загрузка аналитики…</p>
        <p v-else-if="!programsCatalog.length" class="text-sm text-charcoal/55">Нет направлений в справочнике витрины.</p>
        <div v-else-if="programCodeA.trim()" class="grid gap-4 lg:grid-cols-2">
          <article
            v-for="row in programAnalytics"
            :key="row.program_code"
            class="flex flex-col gap-3 rounded-2xl border border-charcoal/10 bg-ivory/40 p-4 shadow-sm"
          >
            <div class="flex flex-wrap items-start justify-between gap-3 border-b border-charcoal/10 pb-3">
              <div class="min-w-0">
                <p class="text-sm font-semibold leading-snug text-charcoal">{{ row.program_name }}</p>
                <p class="text-xs text-charcoal/55">{{ row.program_code }}</p>
              </div>
              <div class="flex flex-wrap gap-3 text-right text-xs text-charcoal/70">
                <span class="inline-flex items-center gap-1">
                  <svg class="h-3.5 w-3.5 shrink-0 text-charcoal/40" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path d="M2 12h12M3 6l3 3 3-4 4 5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                  Ср. ЗП <span class="block font-semibold text-charcoal">{{ moneyFmt.format(row.avg_salary) }} ₽</span>
                </span>
                <span class="inline-flex items-center gap-1">
                  <svg class="h-3.5 w-3.5 shrink-0 text-charcoal/40" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <rect x="2" y="3" width="12" height="10" rx="1" stroke="currentColor" stroke-width="1.2" />
                    <path d="M5 7h6M5 10h4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
                  </svg>
                  Трудоустр. <span class="block font-semibold text-charcoal">{{ pctFmt(row.employment_rate) }}</span>
                </span>
                <span class="inline-flex items-center gap-1">
                  <svg class="h-3.5 w-3.5 shrink-0 text-charcoal/40" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <circle cx="8" cy="8" r="5" stroke="currentColor" stroke-width="1.2" />
                    <circle cx="8" cy="8" r="1.5" fill="currentColor" />
                  </svg>
                  По спец. <span class="block font-semibold text-charcoal">{{ pctFmt(row.specialty_rate) }}</span>
                </span>
              </div>
            </div>
            <div v-if="row.salary_by_year.length" class="h-52 min-h-[12rem] w-full min-w-0">
              <Line :data="programLineData(row)" :options="programLineOptionsShort" />
            </div>
            <p v-else class="py-6 text-center text-xs text-charcoal/55">Нет ряда зарплат по годам для этого вуза.</p>
          </article>
        </div>
      </section>

      <section
        class="rounded-2xl border border-matte-lilac/50 bg-gradient-to-br from-[#f2eef9] via-white to-[#e8f1ec] p-4 shadow-soft sm:p-6"
      >
        <h2 class="mb-1 text-lg font-semibold text-charcoal sm:text-xl">Выпускники по работодателям</h2>
        <p class="mb-4 text-xs text-charcoal/65 sm:text-sm">Топ работодателей по числу выпускников вуза (с учётом фильтра по направлению).</p>
        <div v-if="employers.length" class="h-[min(32rem,75vh)] min-h-[18rem] w-full min-w-0">
          <BarChart
            :labels="employers.map((e) => (e.company_name.length > 42 ? `${e.company_name.slice(0, 40)}…` : e.company_name))"
            :data="employers.map((e) => e.graduates_count)"
            :x-axis="employerXAxis"
          />
        </div>
        <p v-else class="py-10 text-center text-sm text-charcoal/55">Нет данных по работодателям.</p>
      </section>
    </template>
  </section>
</template>
